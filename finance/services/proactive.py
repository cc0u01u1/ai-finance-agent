"""Proactive insight service.

Lightweight, push-style insights (v1 ships exactly three kinds):
    1. Spending growth  - a category runs above its historical daily average
    2. Budget risk      - current burn rate projects an overrun by month end
    3. Possible anomaly - one transaction far above its category history

Unlike InsightService (a full on-demand diagnostic report), these are short
single-sentence nudges. Anomalies are only ever described as "possible",
never as fraud.
"""
import calendar
from datetime import datetime
from typing import List, Optional

from finance.models.enums import TransactionType
from finance.models.insight import Insight
from finance.services.categories import category_label

# Rule thresholds (v1)
GROWTH_PCT_THRESHOLD = 30.0      # current daily avg must exceed history by 30%
MIN_HISTORY_DAYS = 14            # need at least two weeks of history
MIN_HISTORY_TX = 2               # and at least two transactions in category
ANOMALY_MIN_SAMPLE = 4           # category history size before flagging
ANOMALY_RATIO = 2.0              # amount must be >= 2x historical mean
BUDGET_PROJECT_RATIO = 1.0       # projected spend must reach 100% of budget


class ProactiveInsightService:
    @classmethod
    def generate(cls, deps, now: Optional[datetime] = None) -> List[Insight]:
        """Evaluate the three proactive rules against the current month."""
        ref = now or datetime.now()

        # Current month window
        start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            next_start = start.replace(year=start.year + 1, month=1)
        else:
            next_start = start.replace(month=start.month + 1)
        elapsed_days = (ref - start).days + 1
        total_days = (next_start - start).days

        expenses = [
            t for t in deps.expense_repo.list_all()
            if t.type == TransactionType.EXPENSE
        ]

        history = [t for t in expenses if t.date < start]
        current = [
            t for t in expenses
            if start <= t.date < next_start and t.date <= ref
        ]

        insights: List[Insight] = []

        growth = cls._spending_growth(history, current, elapsed_days)
        if growth:
            insights.append(growth)

        budget = cls._budget_risk(deps, current, elapsed_days, total_days, start)
        if budget:
            insights.append(budget)

        anomaly = cls._possible_anomaly(history, current)
        if anomaly:
            insights.append(anomaly)

        return insights

    # -- Rule 1: category spending growth ---------------------------------

    @classmethod
    def _spending_growth(cls, history, current, elapsed_days) -> Optional[Insight]:
        hist_months = {(t.date.year, t.date.month) for t in history}
        hist_days = sum(calendar.monthrange(y, m)[1] for y, m in hist_months)
        if hist_days < MIN_HISTORY_DAYS:
            return None

        hist_by_cat: dict = {}
        for tx in history:
            cat = tx.category.value if tx.category else 'other'
            hist_by_cat[cat] = hist_by_cat.get(cat, 0.0) + tx.amount

        cur_by_cat: dict = {}
        for tx in current:
            cat = tx.category.value if tx.category else 'other'
            cur_by_cat[cat] = cur_by_cat.get(cat, 0.0) + tx.amount

        best = None
        for cat, cur_total in cur_by_cat.items():
            hist_total = hist_by_cat.get(cat, 0.0)
            hist_count = sum(
                1 for t in history
                if (t.category.value if t.category else 'other') == cat
            )
            if hist_total <= 0 or hist_count < MIN_HISTORY_TX:
                continue
            cur_daily = cur_total / elapsed_days
            hist_daily = hist_total / hist_days
            pct = (cur_daily - hist_daily) / hist_daily * 100.0
            if pct >= GROWTH_PCT_THRESHOLD and (best is None or pct > best[1]):
                best = (cat, pct)

        if best is None:
            return None
        cat, pct = best
        return Insight(
            code='PROACTIVE_SPENDING_GROWTH',
            severity='warning',
            title='消费增长',
            category=cat,
            message=f"{category_label(cat)}消费比历史平均增加 {pct:.0f}%。",
            data={'change_pct': round(pct, 1)}
        )

    # -- Rule 2: budget risk based on burn rate ---------------------------

    @classmethod
    def _budget_risk(cls, deps, current, elapsed_days, total_days, start) -> Optional[Insight]:
        budget_repo = getattr(deps, 'budget_repo', None)
        if budget_repo is None:
            return None
        label = f"{start.year:04d}-{start.month:02d}"
        budget = budget_repo.get_for_period(label)
        if budget is None:
            return None

        spent = sum(t.amount for t in current)
        projected = spent / elapsed_days * total_days
        budget_total = budget.total_allocated
        if budget_total <= 0 or projected < budget_total * BUDGET_PROJECT_RATIO:
            return None

        return Insight(
            code='PROACTIVE_BUDGET_RISK',
            severity='warning',
            title='预算风险',
            message=(
                "按目前消费速度，本月可能超过预算"
                f"（预计 ¥{projected:,.0f}，预算 ¥{budget_total:,.0f}）。"
            ),
            data={
                'projected': round(projected, 2),
                'budget_total': round(budget_total, 2)
            }
        )

    # -- Rule 3: single transaction vs category history -------------------

    @classmethod
    def _possible_anomaly(cls, history, current) -> Optional[Insight]:
        by_cat: dict = {}
        for tx in history:
            cat = tx.category.value if tx.category else 'other'
            by_cat.setdefault(cat, []).append(tx.amount)

        best = None
        for tx in current:
            cat = tx.category.value if tx.category else 'other'
            samples = by_cat.get(cat, [])
            if len(samples) < ANOMALY_MIN_SAMPLE:
                continue
            mean = sum(samples) / len(samples)
            if mean <= 0 or tx.amount < mean * ANOMALY_RATIO:
                continue
            ratio = tx.amount / mean
            if best is None or ratio > best[0]:
                best = (ratio, cat, tx.amount, mean)

        if best is None:
            return None
        _, cat, amount, mean = best
        return Insight(
            code='PROACTIVE_POSSIBLE_ANOMALY',
            severity='warning',
            title='可能异常消费',
            category=cat,
            message=(
                "发现一笔明显高于历史平均水平的消费"
                f"（¥{amount:,.0f}，历史平均 ¥{mean:,.0f}），可能异常。"
            ),
            data={'amount': round(amount, 2), 'history_mean': round(mean, 2)}
        )

    # -- Rendering ---------------------------------------------------------

    @staticmethod
    def format_insights(insights: List[Insight]) -> str:
        """Render proactive insights as a compact Chinese reminder card."""
        lines = ["### 🔔 主动提醒", ""]
        if not insights:
            lines.append("✅ 近期没有需要提醒你的事项。")
            return "\n".join(lines)
        for item in insights:
            lines.append(f"🟠 {item.message}")
        return "\n".join(lines)

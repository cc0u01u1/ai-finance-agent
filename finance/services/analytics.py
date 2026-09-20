"""Analytics service: period summaries and period-over-period comparison."""
from datetime import datetime
from typing import List, Optional, Dict
from finance.models.transaction import Transaction
from finance.models.enums import TransactionType
from finance.models.analytics import (
    PeriodSummary, CategoryStat, PeriodComparison, CategoryDelta
)
from finance.services.categories import category_label
from finance.utils.periods import days_in_period


class AnalyticsService:
    @staticmethod
    def _in_range(tx: Transaction, start: datetime, end: datetime) -> bool:
        return start <= tx.date < end

    @classmethod
    def summarize(
        cls,
        transactions: List[Transaction],
        start: datetime,
        end: datetime,
        label: str
    ) -> PeriodSummary:
        """Aggregate income/expense within [start, end)."""
        period_txs = [t for t in transactions if cls._in_range(t, start, end)]
        expenses = [t for t in period_txs if t.type == TransactionType.EXPENSE]
        incomes = [t for t in period_txs if t.type == TransactionType.INCOME]

        total_expense = sum(t.amount for t in expenses)
        total_income = sum(t.amount for t in incomes)

        category_totals: Dict[str, float] = {}
        category_counts: Dict[str, int] = {}
        for t in expenses:
            cat = t.category.value if t.category else 'other'
            category_totals[cat] = category_totals.get(cat, 0.0) + t.amount
            category_counts[cat] = category_counts.get(cat, 0) + 1

        categories: List[CategoryStat] = []
        for cat, amount in sorted(
            category_totals.items(), key=lambda kv: kv[1], reverse=True
        ):
            pct = (amount / total_expense * 100) if total_expense > 0 else 0.0
            categories.append(CategoryStat(
                category=cat,
                amount=round(amount, 2),
                count=category_counts[cat],
                percentage=round(pct, 1)
            ))

        days = days_in_period(start, end)
        savings_rate = ((total_income - total_expense) / total_income) if total_income > 0 else 0.0

        return PeriodSummary(
            period=label,
            start=start,
            end=end,
            total_expense=round(total_expense, 2),
            total_income=round(total_income, 2),
            net=round(total_income - total_expense, 2),
            transaction_count=len(period_txs),
            days=days,
            avg_daily_expense=round(total_expense / days, 2),
            savings_rate=round(savings_rate, 4),
            categories=categories
        )

    @staticmethod
    def compare(
        current: PeriodSummary,
        previous: PeriodSummary
    ) -> PeriodComparison:
        """Compare two period summaries."""
        all_categories = sorted(
            {s.category for s in current.categories}
            | {s.category for s in previous.categories}
        )

        deltas: List[CategoryDelta] = []
        for cat in all_categories:
            cur = current.category_amount(cat)
            prev = previous.category_amount(cat)
            change_pct = ((cur - prev) / prev * 100) if prev > 0 else None
            deltas.append(CategoryDelta(
                category=cat,
                current=round(cur, 2),
                previous=round(prev, 2),
                delta=round(cur - prev, 2),
                change_pct=None if change_pct is None else round(change_pct, 1)
            ))

        deltas.sort(key=lambda d: abs(d.delta), reverse=True)

        total_change_pct = None
        if previous.total_expense > 0:
            total_change_pct = round(
                (current.total_expense - previous.total_expense)
                / previous.total_expense * 100, 1
            )

        return PeriodComparison(
            current_period=current.period,
            base_period=previous.period,
            current_total=current.total_expense,
            previous_total=previous.total_expense,
            delta=round(current.total_expense - previous.total_expense, 2),
            change_pct=total_change_pct,
            current_income=current.total_income,
            previous_income=previous.total_income,
            income_delta=round(current.total_income - previous.total_income, 2),
            categories=deltas
        )

    @staticmethod
    def format_summary(summary: PeriodSummary) -> str:
        """Render a Chinese markdown spending report."""
        lines = [
            f"## 📊 {summary.period} 消费分析",
            "",
            f"- 总支出：**¥{summary.total_expense:,.2f}**",
            f"- 总收入：¥{summary.total_income:,.2f}",
            f"- 净结余：¥{summary.net:,.2f}",
            f"- 日均支出：¥{summary.avg_daily_expense:,.2f}",
            f"- 储蓄率：{summary.savings_rate * 100:.1f}%",
            f"- 交易笔数：{summary.transaction_count}",
            ""
        ]

        if not summary.categories:
            lines.append("_本周期暂无支出记录。_")
            return "\n".join(lines)

        lines.append("| 类别 | 金额 | 占比 | 笔数 |")
        lines.append("| :--- | ---: | ---: | ---: |")
        for stat in summary.categories:
            lines.append(
                f"| {category_label(stat.category)} | ¥{stat.amount:,.2f} "
                f"| {stat.percentage:.1f}% | {stat.count} |"
            )
        return "\n".join(lines)

    @staticmethod
    def format_comparison(comparison: PeriodComparison) -> str:
        """Render a Chinese markdown period comparison."""
        arrow = "↑" if comparison.delta > 0 else ("↓" if comparison.delta < 0 else "→")
        change_text = (
            f"{comparison.change_pct:+.1f}%"
            if comparison.change_pct is not None else "无基数"
        )
        lines = [
            f"## ⚖️ 消费对比：{comparison.base_period} → {comparison.current_period}",
            "",
            f"- 总支出：¥{comparison.previous_total:,.2f} → "
            f"**¥{comparison.current_total:,.2f}**",
            f"- 变化：{arrow} ¥{comparison.delta:,.2f}（{change_text}）",
            f"- 收入变化：¥{comparison.income_delta:,.2f}",
            "",
            "| 类别 | 上期 | 本期 | 变化 | 幅度 |",
            "| :--- | ---: | ---: | ---: | ---: |"
        ]

        for item in comparison.categories:
            d_arrow = "↑" if item.delta > 0 else ("↓" if item.delta < 0 else "→")
            pct_text = (
                f"{item.change_pct:+.1f}%"
                if item.change_pct is not None else "—"
            )
            lines.append(
                f"| {category_label(item.category)} | ¥{item.previous:,.2f} "
                f"| ¥{item.current:,.2f} | {d_arrow} ¥{item.delta:,.2f} "
                f"| {pct_text} |"
            )
        return "\n".join(lines)

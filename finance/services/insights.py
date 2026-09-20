"""Insight service.

Implements the core pipeline:
    financial data -> rules/analysis -> Insight(s) -> agent -> user
"""
from datetime import datetime
from typing import List, Optional
from finance.models.transaction import Transaction
from finance.models.enums import TransactionType
from finance.models.insight import Insight, InsightReport
from finance.services.analytics import AnalyticsService
from finance.services.anomaly import AnomalyService
from finance.services.budgets import BudgetService
from finance.services.categories import category_label
from finance.risk import concentration_hhi
from finance.utils.periods import resolve_period, previous_period

# Rule thresholds
BUDGET_OVERRUN = 1.0
BUDGET_NEAR = 0.8
SPENDING_SURGE_PCT = 20.0
SPENDING_DROP_PCT = -10.0
LOW_SAVINGS_RATE = 0.1
GOOD_SAVINGS_RATE = 0.2
HHI_WARNING = 0.4
MAX_INSIGHTS = 8


class InsightService:
    @classmethod
    def generate(
        cls,
        deps,
        period_expression: Optional[str] = None,
        now: Optional[datetime] = None
    ) -> InsightReport:
        """Run all insight rules against the user's financial data."""
        ref = now or datetime.now()
        start, end, label = resolve_period(period_expression, ref)
        p_start, p_end, p_label = previous_period(start, end, label)

        expenses = deps.expense_repo.list_all()
        income = deps.income_repo.list_all()
        transactions = expenses + income

        current = AnalyticsService.summarize(transactions, start, end, label)
        previous = AnalyticsService.summarize(transactions, p_start, p_end, p_label)
        comparison = AnalyticsService.compare(current, previous)

        current_expenses = [
            t for t in transactions
            if t.type == TransactionType.EXPENSE and start <= t.date < end
        ]
        previous_expenses = [
            t for t in transactions
            if t.type == TransactionType.EXPENSE and p_start <= t.date < p_end
        ]

        budget = None
        if getattr(deps, 'budget_repo', None) is not None:
            budget = deps.budget_repo.get_for_period(label)

        insights: List[Insight] = []
        seen = set()

        def add(insight: Insight):
            key = (insight.code, insight.category)
            if key not in seen:
                seen.add(key)
                insights.append(insight)

        # Rule group 1: budget vs actual
        if budget:
            for row in BudgetService.budget_status(budget, current_expenses):
                cat = row['category']
                if row['usage_pct'] >= BUDGET_OVERRUN and row['planned'] > 0:
                    add(Insight(
                        code='BUDGET_OVERRUN',
                        severity='critical',
                        title='预算超支',
                        category=cat,
                        message=(
                            f"{category_label(cat)}已花 ¥{row['spent']:,.2f}，"
                            f"超出预算 ¥{row['planned']:,.2f}，"
                            f"多用 ¥{-row['remaining']:,.2f}"
                        ),
                        suggestion="后续同类消费先缓一缓，或从其他类别匀一部分额度。",
                        data={'usage_pct': row['usage_pct']}
                    ))
                elif row['usage_pct'] >= BUDGET_NEAR and row['planned'] > 0:
                    add(Insight(
                        code='BUDGET_NEAR',
                        severity='warning',
                        title='预算接近上限',
                        category=cat,
                        message=(
                            f"{category_label(cat)}预算已用 {row['usage_pct'] * 100:.0f}%，"
                            f"只剩 ¥{row['remaining']:,.2f}"
                        ),
                        suggestion="周期还有一段时间，建议控制该类别消费节奏。",
                        data={'usage_pct': row['usage_pct']}
                    ))

        # Rule group 2: statistical anomalies
        for anomaly in AnomalyService.detect(current_expenses, previous_expenses):
            title = {
                'large_transaction': '大额消费',
                'category_outlier': '类别异常',
                'category_spike': '消费激增'
            }.get(anomaly.kind, '消费异常')
            add(Insight(
                code=f"ANOMALY_{anomaly.kind.upper()}",
                severity=anomaly.severity,
                title=title,
                category=anomaly.category,
                message=anomaly.message,
                suggestion="确认这笔消费是否必要，必要时纳入下月预算。",
                data={'score': anomaly.score or 0.0}
            ))

        # Rule group 3: total spending trend
        if comparison.change_pct is not None:
            if comparison.change_pct >= SPENDING_SURGE_PCT:
                add(Insight(
                    code='SPENDING_SURGE',
                    severity='warning',
                    title='支出明显上升',
                    message=(
                        f"总支出较上周期增加 {comparison.change_pct:.0f}%"
                        f"（¥{comparison.delta:,.2f}）"
                    ),
                    suggestion="看看是哪几类涨得最多，非必要开支可以收一收。"
                ))
            elif comparison.change_pct <= SPENDING_DROP_PCT:
                add(Insight(
                    code='SPENDING_DROP',
                    severity='info',
                    title='支出有所下降',
                    message=(
                        f"总支出较上周期减少 {abs(comparison.change_pct):.0f}%"
                        f"（¥{abs(comparison.delta):,.2f}），继续保持。"
                    )
                ))

        # Rule group 4: savings rate
        if current.total_income > 0:
            if current.savings_rate < 0:
                add(Insight(
                    code='NEGATIVE_SAVINGS',
                    severity='critical',
                    title='入不敷出',
                    message=(
                        f"本周期花得比赚得多 ¥{abs(current.net):,.2f}，"
                        f"储蓄率 {current.savings_rate * 100:.0f}%"
                    ),
                    suggestion="先保证必要开支，暂缓非刚需消费，争取下月转正。"
                ))
            elif current.savings_rate < LOW_SAVINGS_RATE:
                add(Insight(
                    code='LOW_SAVINGS',
                    severity='warning',
                    title='储蓄率偏低',
                    message=f"储蓄率仅 {current.savings_rate * 100:.0f}%，建议目标 20% 以上。",
                    suggestion="收入到账时先转出一笔储蓄，再安排消费。"
                ))
            elif current.savings_rate >= GOOD_SAVINGS_RATE:
                add(Insight(
                    code='GOOD_SAVINGS',
                    severity='info',
                    title='储蓄表现不错',
                    message=f"储蓄率达到 {current.savings_rate * 100:.0f}%，保持这个节奏。"
                ))

        # Rule group 5: spending concentration
        if len(current.categories) >= 2:
            amounts = [stat.amount for stat in current.categories]
            hhi = concentration_hhi(amounts)
            if hhi >= HHI_WARNING:
                add(Insight(
                    code='CONCENTRATION',
                    severity='warning',
                    title='消费过于集中',
                    message=(
                        f"支出集中在少数类别（集中度 {hhi:.2f}），"
                        f"结构弹性较差，一旦该类别涨价压力会很明显。"
                    ),
                    suggestion="关注大额固定开支是否有优化空间。"
                ))

        # Fallback: everything looks stable
        if not insights and current.transaction_count > 0:
            add(Insight(
                code='ALL_STABLE',
                severity='info',
                title='财务状况平稳',
                message="未发现超预算、异常消费或明显结构问题，继续保持。"
            ))

        severity_rank = {'critical': 0, 'warning': 1, 'info': 2}
        insights.sort(key=lambda i: severity_rank.get(i.severity, 3))

        return InsightReport(
            period=label,
            generated_at=ref,
            total_expense=current.total_expense,
            total_income=current.total_income,
            net=current.net,
            insights=insights[:MAX_INSIGHTS]
        )

    @staticmethod
    def format_report(report: InsightReport) -> str:
        """Render insights as Chinese markdown for the user."""
        lines = [
            f"## 💡 {report.period} 财务洞察",
            "",
            f"收入 ¥{report.total_income:,.2f}　支出 ¥{report.total_expense:,.2f}"
            f"　净结余 ¥{report.net:,.2f}",
            ""
        ]

        if not report.insights:
            lines.append("_暂无可用数据，先记几笔账，我就能帮你分析了。_")
            return "\n".join(lines)

        lines.append(
            f"🔴 {report.critical_count} 严重　🟠 {report.warning_count} 提醒"
            f"　🔵 {report.info_count} 良好"
        )
        lines.append("")

        icon = {'critical': '🔴', 'warning': '🟠', 'info': '🔵'}
        for item in report.insights:
            lines.append(
                f"{icon.get(item.severity, '🔵')} **{item.title}**　{item.message}"
            )
            if item.suggestion:
                lines.append(f"> 建议：{item.suggestion}")
            lines.append("")

        return "\n".join(lines).rstrip()

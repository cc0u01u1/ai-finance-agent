"""Budget domain service: create budgets from real history and track execution."""
from typing import List, Dict, Optional
from finance.models.transaction import Transaction
from finance.models.budget import Budget
from finance.repositories.budget_repository import BudgetRepository
from finance.services.categories import category_label
from finance.utils.periods import month_label

INCOME_BUFFER_RATIO = 0.9  # leave ~10% headroom when scaling history to income


class BudgetService:
    @staticmethod
    def derive_allocations(
        history_expenses: List[Transaction],
        monthly_income: float
    ) -> Dict[str, float]:
        """Estimate a feasible per-category budget from prior spending."""
        months = {month_label(t.date) for t in history_expenses}
        month_count = max(len(months), 1)

        totals: Dict[str, float] = {}
        for tx in history_expenses:
            cat = tx.category.value if tx.category else 'other'
            totals[cat] = totals.get(cat, 0.0) + tx.amount

        averages = {cat: total / month_count for cat, total in totals.items()}
        total_avg = sum(averages.values())

        target = monthly_income * INCOME_BUFFER_RATIO if monthly_income > 0 else 0.0
        scale = (target / total_avg) if target > 0 and total_avg > target else 1.0

        allocations = {
            cat: round(amount * scale, 2)
            for cat, amount in sorted(averages.items(), key=lambda kv: kv[1], reverse=True)
            if round(amount * scale, 2) > 0
        }
        return allocations

    @classmethod
    def create(
        cls,
        repo: BudgetRepository,
        period: str,
        monthly_income: float,
        allocations: Optional[Dict[str, float]] = None,
        history_expenses: Optional[List[Transaction]] = None
    ) -> Budget:
        """Create or replace the budget for a period."""
        allocations = allocations or None
        if not allocations:
            allocations = cls.derive_allocations(history_expenses or [], monthly_income)

        budget = Budget(
            period=period,
            monthly_income=monthly_income,
            allocations=allocations
        )
        return repo.upsert(budget)

    @staticmethod
    def budget_status(budget: Budget, period_expenses: List[Transaction]) -> List[dict]:
        """Compare planned allocations with actual spending."""
        spent: Dict[str, float] = {}
        for tx in period_expenses:
            cat = tx.category.value if tx.category else 'other'
            spent[cat] = spent.get(cat, 0.0) + tx.amount

        result = []
        categories = set(budget.allocations) | set(spent)
        for cat in categories:
            planned = budget.allocations.get(cat, 0.0)
            actual = spent.get(cat, 0.0)
            usage = (actual / planned) if planned > 0 else 0.0
            result.append({
                'category': cat,
                'planned': round(planned, 2),
                'spent': round(actual, 2),
                'remaining': round(planned - actual, 2),
                'usage_pct': round(usage, 4)
            })
        result.sort(key=lambda r: r['usage_pct'], reverse=True)
        return result

    @staticmethod
    def format_budget(budget: Budget) -> str:
        lines = [
            f"## 🎯 {budget.period} 预算已创建",
            "",
            f"- 月收入：¥{budget.monthly_income:,.2f}",
            f"- 计划支出：¥{budget.total_allocated:,.2f}",
            "",
            "| 类别 | 预算 |",
            "| :--- | ---: |"
        ]
        for cat, amount in sorted(
            budget.allocations.items(), key=lambda kv: kv[1], reverse=True
        ):
            lines.append(f"| {category_label(cat)} | ¥{amount:,.2f} |")
        return "\n".join(lines)

    @staticmethod
    def format_status(budget: Budget, status_rows: List[dict]) -> str:
        lines = [
            f"## 📋 {budget.period} 预算执行进度",
            "",
            "| 类别 | 预算 | 已花 | 剩余 | 使用率 |",
            "| :--- | ---: | ---: | ---: | ---: |"
        ]
        for row in status_rows:
            lines.append(
                f"| {category_label(row['category'])} | ¥{row['planned']:,.2f} "
                f"| ¥{row['spent']:,.2f} | ¥{row['remaining']:,.2f} "
                f"| {row['usage_pct'] * 100:.0f}% |"
            )
        return "\n".join(lines)

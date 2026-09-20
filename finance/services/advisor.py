from typing import List
from finance.models.transaction import Transaction
from finance.models.reports import FinancialReport, BudgetReport

class AdvisorService:
    @staticmethod
    def analyze_spending(expenses: List[Transaction]) -> FinancialReport:
        """
        Analyze current spending and produce a financial report.
        """
        if not expenses:
            return FinancialReport(
                total_spent=0,
                categories={},
                top_category="",
                recommendations=["Start recording expenses to see an analysis."]
            )
        
        total = sum(e.amount for e in expenses)
        category_totals = {}
        for e in expenses:
            cat = e.category.value
            category_totals[cat] = category_totals.get(cat, 0) + e.amount
            
        top_cat = max(category_totals, key=category_totals.get)
        
        return FinancialReport(
            total_spent=total,
            categories=category_totals,
            top_category=top_cat,
            recommendations=[
                f"Your top spending category is {top_cat}.",
                "Consider the 50/30/20 rule: 50% Needs, 30% Wants, 20% Savings."
            ]
        )

    @staticmethod
    def get_budget_advice(monthly_income: float) -> BudgetReport:
        """
        Provide professional budget allocation advice based on income.
        """
        return BudgetReport(
            monthly_income=monthly_income,
            needs=monthly_income * 0.5,
            wants=monthly_income * 0.3,
            savings=monthly_income * 0.2,
            advice=[
                "Stick to $%.2f for your essential needs (rent, utilities)." % (monthly_income * 0.5),
                "Limit lifestyle spending to $%.2f." % (monthly_income * 0.3),
                "Automate $%.2f into savings immediately." % (monthly_income * 0.2)
            ]
        )

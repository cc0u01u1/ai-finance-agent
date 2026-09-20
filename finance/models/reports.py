from pydantic import BaseModel
from typing import List, Dict
from finance.models.enums import TransactionCategory

class FinancialReport(BaseModel):
    total_spent: float
    categories: Dict[str, float]
    top_category: str
    recommendations: List[str]

class BudgetReport(BaseModel):
    monthly_income: float
    needs: float
    wants: float
    savings: float
    advice: List[str]

class SpendingSummary(BaseModel):
    category: TransactionCategory
    total_amount: float
    expense_count: int
    percentage: float

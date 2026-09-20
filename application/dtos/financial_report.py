# application/dtos/financial_report.py
from pydantic import BaseModel
from typing import List

class FinancialReport(BaseModel):
    total_spent: float
    categories: dict[str, float]
    top_category: str
    recommendations: List[str]

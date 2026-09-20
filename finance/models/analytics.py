"""Structured models for spending analytics and period comparison."""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel


class CategoryStat(BaseModel):
    category: str
    amount: float
    count: int
    percentage: float


class PeriodSummary(BaseModel):
    period: str
    start: datetime
    end: datetime
    total_expense: float
    total_income: float
    net: float
    transaction_count: int
    days: int
    avg_daily_expense: float
    savings_rate: float
    categories: List[CategoryStat]

    def category_amount(self, category: str) -> float:
        for stat in self.categories:
            if stat.category == category:
                return stat.amount
        return 0.0


class CategoryDelta(BaseModel):
    category: str
    current: float
    previous: float
    delta: float
    change_pct: Optional[float] = None


class PeriodComparison(BaseModel):
    current_period: str
    base_period: str
    current_total: float
    previous_total: float
    delta: float
    change_pct: Optional[float] = None
    current_income: float
    previous_income: float
    income_delta: float
    categories: List[CategoryDelta]

    def notable_deltas(self, min_change_pct: float = 20.0) -> List[CategoryDelta]:
        result = []
        for item in self.categories:
            if item.change_pct is not None and abs(item.change_pct) >= min_change_pct:
                result.append(item)
        return result

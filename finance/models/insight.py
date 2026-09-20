"""Insight models: the unit of proactive financial communication."""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel


class Insight(BaseModel):
    code: str                         # stable rule code, e.g. 'BUDGET_OVERRUN'
    severity: str                     # info | warning | critical
    title: str
    message: str
    suggestion: Optional[str] = None
    category: Optional[str] = None
    data: Dict[str, float] = {}


class InsightReport(BaseModel):
    period: str
    generated_at: datetime
    total_expense: float
    total_income: float
    net: float
    insights: List[Insight]

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.insights if i.severity == 'critical')

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.insights if i.severity == 'warning')

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.insights if i.severity == 'info')

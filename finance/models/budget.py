"""Budget domain model."""
from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel


class Budget(BaseModel):
    id: Optional[int] = None
    period: str                       # monthly label, e.g. '2026-09'
    monthly_income: float = 0.0
    allocations: Dict[str, float]     # category -> planned amount
    created_at: Optional[datetime] = None

    @property
    def total_allocated(self) -> float:
        return round(sum(self.allocations.values()), 2)

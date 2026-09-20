"""Anomaly detection result models."""
from typing import Optional
from pydantic import BaseModel


class Anomaly(BaseModel):
    kind: str               # large_transaction | category_outlier | category_spike
    severity: str           # info | warning | critical
    category: Optional[str] = None
    amount: Optional[float] = None
    expected: Optional[float] = None
    score: Optional[float] = None
    message: str

# finance/models/finance_goal.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class FinancialGoal(BaseModel):
    name: str
    target_amount: float
    deadline: Optional[datetime] = None
    priority: int = 1  # 1-5, 1 being highest
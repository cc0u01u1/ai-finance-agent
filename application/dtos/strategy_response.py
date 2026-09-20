# application/dtos/strategy_response.py
from pydantic import BaseModel
from typing import List

class StrategyResponse(BaseModel):
    analysis: str
    steps: List[str]
    confidence_score: float
# domain/risk.py
import statistics
from typing import List


def spending_volatility(amounts: List[float]) -> float:
    if len(amounts) < 2:
        return 0.0
    return statistics.stdev(amounts)


def concentration_hhi(amounts: List[float]) -> float:
    total = sum(amounts)
    if total == 0:
        return 0.0

    shares = [a / total for a in amounts]
    return sum(s ** 2 for s in shares)

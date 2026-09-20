# domain/budget.py
def budget_drift(planned: float, actual: float) -> float:
    if planned <= 0:
        return 0.0
    return (actual - planned) / planned

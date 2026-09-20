"""Repository protocol for budgets."""
from typing import Protocol, Optional, List
from finance.models.budget import Budget


class BudgetRepository(Protocol):
    def get_for_period(self, period: str) -> Optional[Budget]:
        ...

    def upsert(self, budget: Budget) -> Budget:
        ...

    def list_all(self) -> List[Budget]:
        ...

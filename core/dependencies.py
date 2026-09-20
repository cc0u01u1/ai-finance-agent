from dataclasses import dataclass
from typing import Any
from finance.repositories.transaction_repository import TransactionRepository

@dataclass
class FinanceDependencies:
    """
    Aggregates all dependencies required by the Finance Domain logic.
    Using this explicitly makes it clear what the agent needs.
    """
    expense_repo: TransactionRepository
    income_repo: TransactionRepository
    budget_repo: Any = None

@dataclass
class DataEngineDependencies:
    """
    Dependencies for the Data Warehousing Agent.
    """
    pool: Any # asyncpg.Pool


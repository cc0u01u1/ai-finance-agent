# finance/repositories/transaction_repository.py
from typing import Protocol, List, Optional
from datetime import datetime
from finance.models.transaction import Transaction
from finance.models.enums import TransactionType, TransactionCategory

class TransactionRepository(Protocol):

    def add(self, transaction: Transaction) -> Transaction:
        ...

    def list_all(self) -> List[Transaction]:
        ...

    def list_by_type(
        self, transaction_type: TransactionType
    ) -> List[Transaction]:
        ...

    def list_by_category(
        self, category: TransactionCategory
    ) -> List[Transaction]:
        ...

    def list_by_date_range(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Transaction]:
        ...

    def total_amount(
        self,
        transaction_type: Optional[TransactionType] = None
    ) -> float:
        ...

    def clear(self) -> None:
        ...

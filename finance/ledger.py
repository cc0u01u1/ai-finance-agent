# domain/ledger.py
from typing import List
from pydantic import BaseModel, ConfigDict
from .models.transaction import Transaction
from .models.enums import TransactionType


class Ledger(BaseModel):
    model_config = ConfigDict(frozen=True)

    transactions: List[Transaction]

    @property
    def inflow(self) -> float:
        return sum(t.amount for t in self.transactions if t.type == TransactionType.INCOME)

    @property
    def outflow(self) -> float:
        return sum(t.amount for t in self.transactions if t.type == TransactionType.EXPENSE)

    @property
    def net_cashflow(self) -> float:
        return self.inflow - self.outflow

    @property
    def average_burn_rate(self) -> float:
        """
        Calculate the monthly burn rate (average expense).
        """
        if not self.transactions:
            return 0.0
        
        expense_txs = [t for t in self.transactions if t.type == TransactionType.EXPENSE]
        if not expense_txs:
            return 0.0
            
        dates = [t.date for t in expense_txs]
        days_diff = (max(dates) - min(dates)).days or 1
        months = max(days_diff / 30, 1)
        
        return self.outflow / months

    @property
    def financial_runway(self) -> float:
        """
        Months of survival based on net cash balance and burn rate.
        Note: In a real app, this would use 'Net Worth', here we use net surplus as a proxy.
        """
        burn = self.average_burn_rate
        if burn <= 0:
            return float('inf')
        return max(self.net_cashflow / burn, 0.0)

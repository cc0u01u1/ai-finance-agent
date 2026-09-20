from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from finance.models.enums import TransactionType, TransactionCategory

class Transaction(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int | None = None
    type: TransactionType
    amount: float = Field(gt=0)
    category: TransactionCategory | None = None
    description: str
    date: datetime

    @property
    def signed_amount(self) -> float:
        return self.amount if self.type == TransactionType.INCOME else -self.amount

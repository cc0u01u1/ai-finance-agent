# domain/cashflow.py
from pydantic import BaseModel, ConfigDict, Field


class CashFlow(BaseModel):
    model_config = ConfigDict(frozen=True)

    inflow: float = Field(ge=0)
    outflow: float = Field(ge=0)

    @property
    def net(self) -> float:
        return self.inflow - self.outflow

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_SYMBOL_LENGTH = 20


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class TradeRequest(BaseModel):
    coin_symbol: str = Field(max_length=MAX_SYMBOL_LENGTH)
    quantity: Decimal = Field(gt=0)

    @field_validator("coin_symbol")
    @classmethod
    def symbol_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("coin_symbol must not be empty")
        return stripped.upper()


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class PaperAccountResponse(BaseModel):
    id: int
    name: str
    initial_cash: float
    cash_balance: float
    created_at: datetime
    updated_at: datetime


class PaperTransactionResponse(BaseModel):
    id: int
    account_id: int
    coin_symbol: str
    transaction_type: Literal["BUY", "SELL"]
    quantity: float
    execution_price: float
    total_value: float
    realized_profit: float | None
    executed_at: datetime


class PaperHoldingResponse(BaseModel):
    coin_symbol: str
    coin_name: str | None
    image_url: str | None = None
    price_change_percentage_24h: float | None = None
    quantity: float
    average_cost: float
    current_price: float | None
    current_value: float | None
    unrealized_profit: float | None
    unrealized_percent: float | None
    allocation_percent: float | None


class PaperPortfolioResponse(BaseModel):
    account: PaperAccountResponse
    holdings: list[PaperHoldingResponse]
    cash_balance: float
    invested_value: float
    holdings_value: float
    total_equity: float
    realized_profit: float
    unrealized_profit: float
    total_return_percent: float | None
    best_performer: str | None
    worst_performer: str | None

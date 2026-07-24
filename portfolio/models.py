from datetime import datetime

from pydantic import BaseModel, Field, field_validator

MAX_NAME_LENGTH = 200
MAX_SYMBOL_LENGTH = 20


def _non_blank(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")
    return stripped


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class PortfolioCreateRequest(BaseModel):
    name: str = Field(max_length=MAX_NAME_LENGTH)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        return _non_blank(value, "name")

    @field_validator("description")
    @classmethod
    def description_stripped(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PortfolioUpdateRequest(PortfolioCreateRequest):
    """Same shape as create: PUT replaces name/description together (rename included)."""


class HoldingCreateRequest(BaseModel):
    coin_symbol: str = Field(max_length=MAX_SYMBOL_LENGTH)
    quantity: float = Field(gt=0)
    average_buy_price: float = Field(ge=0)

    @field_validator("coin_symbol")
    @classmethod
    def symbol_not_blank(cls, value: str) -> str:
        return _non_blank(value, "coin_symbol").upper()


class HoldingUpdateRequest(BaseModel):
    quantity: float = Field(gt=0)
    average_buy_price: float = Field(ge=0)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class PortfolioResponse(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class HoldingResponse(BaseModel):
    id: int
    portfolio_id: int
    coin_symbol: str
    coin_name: str | None
    image_url: str | None = None
    price_change_percentage_24h: float | None = None
    quantity: float
    average_buy_price: float
    current_price: float | None
    current_value: float | None
    cost_basis: float
    unrealized_profit: float | None
    profit_percent: float | None
    created_at: datetime
    updated_at: datetime


class PortfolioSummary(BaseModel):
    total_value: float
    total_cost_basis: float
    total_unrealized_profit: float
    total_unrealized_percent: float | None


class PortfolioDetailResponse(PortfolioResponse):
    holdings: list[HoldingResponse]
    summary: PortfolioSummary

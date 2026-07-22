from datetime import date

from pydantic import BaseModel


class MarketOverview(BaseModel):
    snapshot_date: date
    coin_count: int
    total_market_cap_usd: float | None
    total_volume_24h_usd: float | None


class CoinSnapshot(BaseModel):
    coin_id: str
    symbol: str
    name: str
    snapshot_date: date
    price_usd: float
    market_cap_usd: float | None
    volume_24h_usd: float | None
    circulating_supply: float | None
    market_cap_rank: int | None


class TopMarketCapEntry(BaseModel):
    market_cap_position: int
    coin_id: str
    symbol: str
    name: str
    snapshot_date: date
    market_cap_usd: float | None
    price_usd: float


class TopVolumeEntry(BaseModel):
    volume_position: int
    coin_id: str
    symbol: str
    name: str
    snapshot_date: date
    volume_24h_usd: float | None
    price_usd: float

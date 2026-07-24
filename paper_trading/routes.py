from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from paper_trading import service
from database import get_connection
from paper_trading.models import (
    PaperAccountResponse,
    PaperPortfolioResponse,
    PaperTransactionResponse,
    TradeRequest,
)

router = APIRouter(tags=["paper-trading"])


def _get_db():
    """Same per-request connection pattern as analytics_routes/portfolio_routes: commits on a
    clean return, rolls back on any exception (including a rejected trade), via psycopg3's own
    connection context-manager semantics. This is also what makes buy/sell atomic — the lock,
    validation, balance update, and transaction insert all share one connection/transaction."""
    try:
        conn = get_connection()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    with conn:
        yield conn


DbDep = Annotated[Connection, Depends(_get_db)]


@router.get(
    "/paper-account",
    response_model=PaperAccountResponse,
    summary="Get the paper-trading account",
    description="Lazily creates the single default paper-trading account on first access. No real money.",
)
def get_paper_account(conn: DbDep) -> PaperAccountResponse:
    return PaperAccountResponse.model_validate(service.get_or_create_account(conn))


@router.post(
    "/paper-account/reset",
    response_model=PaperAccountResponse,
    summary="Reset the paper-trading account",
    description="Restores cash_balance to initial_cash and deletes all transaction history. Irreversible; simulated data only.",
)
def reset_paper_account(conn: DbDep) -> PaperAccountResponse:
    return PaperAccountResponse.model_validate(service.reset_account(conn))


@router.get(
    "/paper-portfolio",
    response_model=PaperPortfolioResponse,
    summary="Full paper-trading valuation",
    description=(
        "Cash balance, holdings (with allocation %), total equity, realized/unrealized P&L, total "
        "return, and best/worst performer. Holdings and cost basis are derived from the immutable "
        "transaction history using the weighted-average-cost method; prices come from the "
        "warehouse's latest snapshot, never CoinGecko directly."
    ),
)
def get_paper_portfolio(conn: DbDep) -> PaperPortfolioResponse:
    return PaperPortfolioResponse.model_validate(service.get_portfolio(conn))


@router.post(
    "/paper-trades/buy",
    response_model=PaperTransactionResponse,
    status_code=201,
    summary="Execute a simulated buy",
    description="Returns 404 if coin_symbol has no current warehouse snapshot, 400 if the cost exceeds the available cash balance.",
)
def buy(body: TradeRequest, conn: DbDep) -> PaperTransactionResponse:
    try:
        result = service.buy(conn, body.coin_symbol, body.quantity)
    except service.UnknownCoinSymbolError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.InsufficientCashError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PaperTransactionResponse.model_validate(result)


@router.post(
    "/paper-trades/sell",
    response_model=PaperTransactionResponse,
    status_code=201,
    summary="Execute a simulated sell",
    description="Returns 404 if coin_symbol has no current warehouse snapshot, 400 if quantity exceeds the currently held amount.",
)
def sell(body: TradeRequest, conn: DbDep) -> PaperTransactionResponse:
    try:
        result = service.sell(conn, body.coin_symbol, body.quantity)
    except service.UnknownCoinSymbolError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.InsufficientHoldingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PaperTransactionResponse.model_validate(result)


@router.get(
    "/paper-trades",
    response_model=list[PaperTransactionResponse],
    summary="Paper-trading transaction history",
    description="Newest first. The full, immutable trade ledger for the default account.",
)
def list_paper_trades(
    conn: DbDep,
    limit: Annotated[int | None, Query(ge=1, le=1000, description="Maximum rows to return. Omit to return all.")] = None,
) -> list[PaperTransactionResponse]:
    rows = service.list_transactions(conn, limit)
    return [PaperTransactionResponse.model_validate(row) for row in rows]

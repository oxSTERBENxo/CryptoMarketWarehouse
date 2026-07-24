from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from psycopg import Connection

from portfolio import service
from database import get_connection
from portfolio.models import (
    HoldingCreateRequest,
    HoldingResponse,
    HoldingUpdateRequest,
    PortfolioCreateRequest,
    PortfolioDetailResponse,
    PortfolioUpdateRequest,
)

router = APIRouter(tags=["portfolio"])


def _get_db():
    """Yield a connection for one request; convert a failure to *connect* into a 503.

    Only `get_connection()` itself is guarded: FastAPI enters this generator before request
    validation runs, and re-throws validation failures into it during cleanup. Wrapping the
    `yield` in the same try/except would misreport those (and any other in-request exception,
    including our own service-layer 404/400s) as 503. The connection still commits on a clean
    return and rolls back if an exception propagates, via psycopg3 Connection's own
    context-manager semantics.
    """
    try:
        conn = get_connection()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    with conn:
        yield conn


DbDep = Annotated[Connection, Depends(_get_db)]


@router.get(
    "/portfolios",
    response_model=list[PortfolioDetailResponse],
    summary="List portfolios",
    description="All portfolios with their holdings and current valuation, priced from the warehouse.",
)
def list_portfolios(conn: DbDep) -> list[PortfolioDetailResponse]:
    return [PortfolioDetailResponse.model_validate(p) for p in service.list_portfolios(conn)]


@router.post(
    "/portfolios",
    response_model=PortfolioDetailResponse,
    status_code=201,
    summary="Create a portfolio",
)
def create_portfolio(body: PortfolioCreateRequest, conn: DbDep) -> PortfolioDetailResponse:
    result = service.create_portfolio(conn, body.name, body.description)
    return PortfolioDetailResponse.model_validate(result)


@router.get(
    "/portfolios/{portfolio_id}",
    response_model=PortfolioDetailResponse,
    summary="Get one portfolio",
    description="Returns 404 if the portfolio does not exist.",
)
def get_portfolio(portfolio_id: int, conn: DbDep) -> PortfolioDetailResponse:
    try:
        result = service.get_portfolio(conn, portfolio_id)
    except service.PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PortfolioDetailResponse.model_validate(result)


@router.put(
    "/portfolios/{portfolio_id}",
    response_model=PortfolioDetailResponse,
    summary="Rename/update a portfolio",
    description="Replaces name and description. Returns 404 if the portfolio does not exist.",
)
def update_portfolio(portfolio_id: int, body: PortfolioUpdateRequest, conn: DbDep) -> PortfolioDetailResponse:
    try:
        result = service.rename_portfolio(conn, portfolio_id, body.name, body.description)
    except service.PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PortfolioDetailResponse.model_validate(result)


@router.delete(
    "/portfolios/{portfolio_id}",
    status_code=204,
    summary="Delete a portfolio",
    description="Cascades to delete all of its holdings. Returns 404 if the portfolio does not exist.",
)
def delete_portfolio(portfolio_id: int, conn: DbDep) -> Response:
    try:
        service.delete_portfolio(conn, portfolio_id)
    except service.PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post(
    "/portfolios/{portfolio_id}/holdings",
    response_model=HoldingResponse,
    status_code=201,
    summary="Add a holding to a portfolio",
    description=(
        "Returns 404 if the portfolio does not exist, 400 if coin_symbol has no current warehouse "
        "snapshot or the portfolio already holds that coin."
    ),
)
def add_holding(portfolio_id: int, body: HoldingCreateRequest, conn: DbDep) -> HoldingResponse:
    try:
        result = service.add_holding(conn, portfolio_id, body.coin_symbol, body.quantity, body.average_buy_price)
    except service.PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (service.UnknownCoinSymbolError, service.DuplicateHoldingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return HoldingResponse.model_validate(result)


@router.put(
    "/holdings/{holding_id}",
    response_model=HoldingResponse,
    summary="Edit a holding",
    description="Updates quantity and average buy price. Returns 404 if the holding does not exist.",
)
def update_holding(holding_id: int, body: HoldingUpdateRequest, conn: DbDep) -> HoldingResponse:
    try:
        result = service.edit_holding(conn, holding_id, body.quantity, body.average_buy_price)
    except service.HoldingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HoldingResponse.model_validate(result)


@router.delete(
    "/holdings/{holding_id}",
    status_code=204,
    summary="Delete a holding",
    description="Returns 404 if the holding does not exist.",
)
def delete_holding(holding_id: int, conn: DbDep) -> Response:
    try:
        service.remove_holding(conn, holding_id)
    except service.HoldingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)

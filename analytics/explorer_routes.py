from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from psycopg import Connection

from analytics import explorer_repository as repo
from analytics import explorer_service as service
from analytics.explorer_models import ExplorerRequest, ExplorerResponse, ExplorerResultRow
from database import get_connection

router = APIRouter(prefix="/analytics/explorer", tags=["analytics-explorer"])

# Hard cap on CSV export size: exports ignore the request's pagination (a paginated CSV would be
# useless) but must not become unbounded as the warehouse grows.
EXPORT_MAX_ROWS = 1000


def _get_db():
    """Yield a connection for one request; convert a failure to *connect* into a 503.

    Only `get_connection()` itself is guarded: FastAPI enters this generator before request
    validation runs, and re-throws validation failures into it during cleanup. Wrapping the
    `yield` in the same try/except would misreport those (e.g. an out-of-range `limit`) as 503
    instead of the correct 422. See analytics_routes._get_db for the original.
    """
    try:
        conn = get_connection()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    with conn:
        yield conn


DbDep = Annotated[Connection, Depends(_get_db)]


def _analyze(conn: Connection, request: ExplorerRequest) -> ExplorerResponse:
    """Shared query pipeline for both endpoints: validate, fetch the per-coin period stats from
    the warehouse once, and run the requested analysis over them."""
    if request.from_date > request.to_date:
        raise HTTPException(status_code=400, detail="from_date must not be later than to_date")

    raw = repo.fetch_period_stats(conn, request.from_date, request.to_date)
    rows = [ExplorerResultRow.model_validate(r) for r in raw]
    try:
        return service.run_analysis(rows, request)
    except (service.UnsupportedAnalysisError, service.MissingThresholdError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/query",
    response_model=ExplorerResponse,
    summary="Run an Analytics Explorer analysis over historical warehouse data",
    description=(
        "Runs one registered analysis (a metric + condition pair, e.g. price + "
        "increased_by_percent) over `analytics.market_history` between `from_date` and "
        "`to_date`, entirely from warehouse data -- no external APIs and no AI. Start/end values "
        "are the first/last real observation loaded inside the range (never estimated); coins "
        "with fewer than 2 observations in range are excluded. Optional value filters (market "
        "cap, average volume, rank range, price range) apply before the analysis condition. "
        "`summary` aggregates every qualifying row, while `rows` is the requested "
        "`offset`/`limit` page of them. Returns 400 for an inverted date range, an unregistered "
        "metric+condition pair, or a missing required threshold."
    ),
)
def run_query(conn: DbDep, request: ExplorerRequest) -> ExplorerResponse:
    return _analyze(conn, request)


@router.post(
    "/export",
    summary="Export an Analytics Explorer analysis as CSV",
    description=(
        "Runs the same analysis as `/analytics/explorer/query` and returns every qualifying row "
        f"(ignoring `offset`/`limit`, capped at {EXPORT_MAX_ROWS}) as a CSV attachment -- the "
        "classic warehouse hand-off into spreadsheet/BI tools."
    ),
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
def export_csv(conn: DbDep, request: ExplorerRequest) -> Response:
    # Re-run with pagination widened to the export cap so the CSV holds the full result set.
    full = request.model_copy(update={"offset": 0, "limit": EXPORT_MAX_ROWS})
    result = _analyze(conn, full)
    csv_text = service.rows_to_csv(result.rows)
    filename = f"analytics-explorer_{request.from_date.isoformat()}_{request.to_date.isoformat()}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

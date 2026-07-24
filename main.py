import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from services import scheduler
from services import startup_recovery
from api.admin_routes import router as admin_router
from ai.routes import router as ai_router
from analytics.explorer_routes import router as analytics_explorer_router
from analytics.routes import router as analytics_router
from database import get_connection
from paper_trading.routes import router as paper_trading_router
from portfolio.routes import router as portfolio_router
from health.models import WarehouseHealthResponse
from health.service import get_warehouse_health

load_dotenv()

# Origins allowed to call this API. Defaults to the common Vite dev server ports so local
# development works unconfigured even when 5173 is taken and Vite falls back to 5174/5175;
# set CORS_ALLOWED_ORIGINS (comma-separated) to add the deployed frontend's origin.
_DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:5174,http://127.0.0.1:5174,"
    "http://localhost:5175,http://127.0.0.1:5175"
)
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", _DEFAULT_ALLOWED_ORIGINS).split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start_scheduler()
    # Part 7/8: startup gap-detection + non-blocking historical backfill. Runs regardless of
    # ENABLE_SCHEDULER (it's about catching up missed daily snapshots, not scheduled collection),
    # but never blocks this startup path or raises -- see startup_recovery.start_recovery_if_needed.
    startup_recovery.start_recovery_if_needed()
    yield
    scheduler.stop_scheduler()


app = FastAPI(title="CryptoMarketWarehouse", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(analytics_router)
app.include_router(analytics_explorer_router)
app.include_router(admin_router)
app.include_router(portfolio_router)
app.include_router(paper_trading_router)
app.include_router(ai_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/health/database")
def health_database() -> dict[str, str]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "healthy"}


@app.get("/health/scheduler")
def health_scheduler() -> dict:
    return scheduler.get_scheduler_status()


@app.get("/health/warehouse")
def health_warehouse() -> WarehouseHealthResponse:
    """Aggregated Warehouse Health / Data Quality view -- see health/service.py. Always
    returns 200 (the payload's own overall_status/per-check status fields carry
    healthy/warning/error/unknown, since a degraded warehouse is still a successful health check,
    not an API error)."""
    with get_connection() as conn:
        return get_warehouse_health(conn)

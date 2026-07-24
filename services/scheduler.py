import os

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from etl.ingest_intraday_market_data import run_intraday_ingest
from utils.logging_config import get_logger
from services.pipeline_runner import PipelineAlreadyRunningError, get_state_snapshot, run_pipeline
from database import get_connection

load_dotenv()

logger = get_logger("scheduler")

JOB_ID = "coingecko_pipeline"
INTRADAY_JOB_ID = "coingecko_intraday"

ENABLE_SCHEDULER = os.environ.get("ENABLE_SCHEDULER", "false").strip().lower() in ("1", "true", "yes")
SCHEDULER_INTERVAL_MINUTES = int(os.environ.get("SCHEDULER_INTERVAL_MINUTES", "60"))
SCHEDULER_CURRENCY = os.environ.get("SCHEDULER_CURRENCY", "usd")
SCHEDULER_LIMIT = int(os.environ.get("SCHEDULER_LIMIT", "100"))
SCHEDULER_ORDER = os.environ.get("SCHEDULER_ORDER", "market_cap_desc")

# Intraday collection is a separate, optional job -- disabled by default so enabling the main
# scheduler never silently adds extra CoinGecko traffic. See etl/ingest_intraday_market_data.py.
ENABLE_INTRADAY_SCHEDULER = os.environ.get("ENABLE_INTRADAY_SCHEDULER", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)
INTRADAY_INTERVAL_MINUTES = int(os.environ.get("INTRADAY_INTERVAL_MINUTES", "60"))
INTRADAY_COINS = [
    c.strip()
    for c in os.environ.get("INTRADAY_COINS", "bitcoin,ethereum,solana,cardano,dogecoin").split(",")
    if c.strip()
]

_scheduler: BackgroundScheduler | None = None


def _run_scheduled_job() -> None:
    try:
        run_pipeline(
            trigger="scheduled",
            currency=SCHEDULER_CURRENCY,
            limit=SCHEDULER_LIMIT,
            order=SCHEDULER_ORDER,
        )
    except PipelineAlreadyRunningError:
        # Already logged inside run_pipeline; nothing further to do here.
        pass


def _run_scheduled_intraday_job() -> None:
    """Runs independently of the daily pipeline's run-lock: intraday ingestion is a handful of
    single-call-per-coin requests, cheap enough not to need mutual exclusion with the main job."""
    conn = get_connection()
    try:
        run_intraday_ingest(conn, INTRADAY_COINS)
    except Exception:
        logger.exception("Scheduled intraday ingest failed")
    finally:
        conn.close()


def start_scheduler() -> None:
    """Start the background scheduler once, if either the daily or intraday job is enabled. Safe
    to call multiple times (no-op if already running, or if both are disabled). The two jobs are
    independent: either can be enabled without the other."""
    global _scheduler

    if not ENABLE_SCHEDULER and not ENABLE_INTRADAY_SCHEDULER:
        logger.info(
            "Scheduler disabled (ENABLE_SCHEDULER=false, ENABLE_INTRADAY_SCHEDULER=false); skipping startup"
        )
        return

    if _scheduler is not None and _scheduler.running:
        logger.info("Scheduler already running; skipping duplicate startup")
        return

    _scheduler = BackgroundScheduler()
    if ENABLE_SCHEDULER:
        _scheduler.add_job(
            _run_scheduled_job,
            trigger="interval",
            minutes=SCHEDULER_INTERVAL_MINUTES,
            id=JOB_ID,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        logger.info("Daily pipeline job scheduled: interval=%d minutes", SCHEDULER_INTERVAL_MINUTES)
    if ENABLE_INTRADAY_SCHEDULER:
        _scheduler.add_job(
            _run_scheduled_intraday_job,
            trigger="interval",
            minutes=INTRADAY_INTERVAL_MINUTES,
            id=INTRADAY_JOB_ID,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        logger.info(
            "Intraday job scheduled: interval=%d minutes, coins=%s",
            INTRADAY_INTERVAL_MINUTES,
            ",".join(INTRADAY_COINS),
        )
    _scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler() -> None:
    """Stop the background scheduler cleanly, if running. Safe to call multiple times."""
    global _scheduler

    if _scheduler is None or not _scheduler.running:
        return

    _scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
    _scheduler = None


def get_scheduler_status() -> dict:
    """Status snapshot for the health endpoint."""
    next_run_time = None
    next_intraday_run_time = None
    running = _scheduler is not None and _scheduler.running
    if running:
        job = _scheduler.get_job(JOB_ID)
        if job is not None and job.next_run_time is not None:
            next_run_time = job.next_run_time
        intraday_job = _scheduler.get_job(INTRADAY_JOB_ID)
        if intraday_job is not None and intraday_job.next_run_time is not None:
            next_intraday_run_time = intraday_job.next_run_time

    state = get_state_snapshot()
    return {
        "enabled": ENABLE_SCHEDULER,
        "running": running,
        "interval_minutes": SCHEDULER_INTERVAL_MINUTES,
        "currently_running": state["currently_running"],
        "last_success_at": state["last_success_at"],
        "last_failure_at": state["last_failure_at"],
        "next_run_time": next_run_time,
        "intraday_enabled": ENABLE_INTRADAY_SCHEDULER,
        "intraday_interval_minutes": INTRADAY_INTERVAL_MINUTES,
        "intraday_next_run_time": next_intraday_run_time,
    }

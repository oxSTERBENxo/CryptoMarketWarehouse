import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

"""Single timezone authority for "what calendar date is today" across the app (Part 9).

Historically, different parts of this codebase picked "today" differently: the live pipeline's
daily snapshot_date derives from a TIMESTAMPTZ (audit.etl_run.started_at, effectively UTC), while
etl/backfill_market_history.py's CLI default (`date.today()`) uses the machine's local date. Both are
left as-is here to avoid touching working, already-idempotent pipeline code. Every *new* piece of
code introduced for startup gap-detection and the manual intraday snapshot (startup_recovery.py,
pipeline_runner.run_pipeline's insert_intraday path) goes through this module instead, so at least
they agree with each other. Configurable via APP_TIMEZONE (default "UTC") for deployments that
want gap-detection/day-boundaries to line up with a specific local market close instead.
"""

APP_TIMEZONE_NAME = os.environ.get("APP_TIMEZONE", "UTC").strip() or "UTC"
APP_TIMEZONE = ZoneInfo(APP_TIMEZONE_NAME)


def now() -> datetime:
    """Current instant, attached to APP_TIMEZONE."""
    return datetime.now(APP_TIMEZONE)


def today() -> date:
    """Today's calendar date in APP_TIMEZONE."""
    return now().date()

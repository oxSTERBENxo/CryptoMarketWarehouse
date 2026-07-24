import importlib

from services import scheduler as scheduler_module


def _reload_scheduler():
    return importlib.reload(scheduler_module)


def test_scheduler_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_SCHEDULER", raising=False)
    module = _reload_scheduler()
    try:
        assert module.ENABLE_SCHEDULER is False
    finally:
        module.stop_scheduler()
        _reload_scheduler()


def test_start_scheduler_noop_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_SCHEDULER", "false")
    module = _reload_scheduler()
    try:
        module.start_scheduler()
        status = module.get_scheduler_status()
        assert status["enabled"] is False
        assert status["running"] is False
    finally:
        module.stop_scheduler()
        _reload_scheduler()


def test_start_scheduler_reads_interval_from_env(monkeypatch):
    monkeypatch.setenv("ENABLE_SCHEDULER", "true")
    monkeypatch.setenv("SCHEDULER_INTERVAL_MINUTES", "15")
    module = _reload_scheduler()
    try:
        assert module.SCHEDULER_INTERVAL_MINUTES == 15
        module.start_scheduler()
        status = module.get_scheduler_status()
        assert status["enabled"] is True
        assert status["running"] is True
        assert status["interval_minutes"] == 15
        assert status["next_run_time"] is not None
    finally:
        module.stop_scheduler()
        _reload_scheduler()


def test_start_scheduler_does_not_duplicate(monkeypatch):
    monkeypatch.setenv("ENABLE_SCHEDULER", "true")
    module = _reload_scheduler()
    try:
        module.start_scheduler()
        first_job = module._scheduler.get_job(module.JOB_ID)
        module.start_scheduler()  # second call must be a no-op, not a second scheduler
        second_job = module._scheduler.get_job(module.JOB_ID)
        assert first_job.id == second_job.id
    finally:
        module.stop_scheduler()
        _reload_scheduler()


def test_stop_scheduler_is_safe_when_not_running(monkeypatch):
    monkeypatch.delenv("ENABLE_SCHEDULER", raising=False)
    module = _reload_scheduler()
    module.stop_scheduler()  # must not raise
    module.stop_scheduler()  # calling twice must also not raise


def test_intraday_scheduler_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_INTRADAY_SCHEDULER", raising=False)
    module = _reload_scheduler()
    try:
        assert module.ENABLE_INTRADAY_SCHEDULER is False
    finally:
        module.stop_scheduler()
        _reload_scheduler()


def test_intraday_scheduler_independent_of_main_scheduler(monkeypatch):
    """Enabling ENABLE_SCHEDULER must never silently also enable intraday collection, and vice
    versa -- the two jobs are controlled by separate env vars."""
    monkeypatch.setenv("ENABLE_SCHEDULER", "true")
    monkeypatch.delenv("ENABLE_INTRADAY_SCHEDULER", raising=False)
    module = _reload_scheduler()
    try:
        module.start_scheduler()
        assert module._scheduler.get_job(module.JOB_ID) is not None
        assert module._scheduler.get_job(module.INTRADAY_JOB_ID) is None
    finally:
        module.stop_scheduler()
        _reload_scheduler()


def test_intraday_scheduler_starts_when_enabled_alone(monkeypatch):
    monkeypatch.delenv("ENABLE_SCHEDULER", raising=False)
    monkeypatch.setenv("ENABLE_INTRADAY_SCHEDULER", "true")
    monkeypatch.setenv("INTRADAY_INTERVAL_MINUTES", "30")
    module = _reload_scheduler()
    try:
        module.start_scheduler()
        status = module.get_scheduler_status()
        assert status["running"] is True
        assert status["intraday_enabled"] is True
        assert status["intraday_interval_minutes"] == 30
        assert status["intraday_next_run_time"] is not None
        assert module._scheduler.get_job(module.JOB_ID) is None
    finally:
        module.stop_scheduler()
        _reload_scheduler()

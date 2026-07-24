from datetime import date, datetime, timezone

import pytest

from etl import load_warehouse as etl


def _sql_kind(sql: str) -> str:
    return " ".join(sql.split())


class _UpsertDimCoinCursor:
    """Fakes the two-query shape upsert_dim_coin uses: one SELECT of the current row, then
    either an INSERT (new coin), or an UPDATE(s) + INSERT (SCD2 change), or nothing further
    (unchanged identity, only a possible in-place image_url UPDATE)."""

    def __init__(self, current_row):
        self.current_row = current_row
        self.executed: list[tuple[str, tuple | None]] = []
        self._next_fetchone = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        kind = _sql_kind(sql)
        self.executed.append((kind, params))
        if kind.startswith("SELECT coin_key, symbol, name, image_url"):
            self._next_fetchone = self.current_row
        elif kind.startswith("INSERT INTO dw.dim_coin"):
            self._next_fetchone = (999,)
        else:
            self._next_fetchone = None

    def fetchone(self):
        return self._next_fetchone


def test_upsert_dim_coin_inserts_new_coin_with_image_url():
    cur = _UpsertDimCoinCursor(current_row=None)

    coin_key, action = etl.upsert_dim_coin(cur, "bitcoin", "btc", "Bitcoin", image_url="https://img/btc.png")

    assert (coin_key, action) == (999, "inserted")
    insert_calls = [p for kind, p in cur.executed if kind.startswith("INSERT INTO dw.dim_coin")]
    assert insert_calls == [("bitcoin", "btc", "Bitcoin", "https://img/btc.png")]


def test_upsert_dim_coin_updates_image_url_in_place_without_new_scd2_version():
    """A logo-only change (symbol/name unchanged) must not create a new dim_coin version --
    just an in-place UPDATE of image_url on the existing row."""
    cur = _UpsertDimCoinCursor(current_row=(1, "btc", "Bitcoin", "https://img/old.png"))

    coin_key, action = etl.upsert_dim_coin(cur, "bitcoin", "btc", "Bitcoin", image_url="https://img/new.png")

    assert (coin_key, action) == (1, "unchanged")
    update_calls = [kind for kind, _ in cur.executed if kind.startswith("UPDATE dw.dim_coin SET image_url")]
    assert len(update_calls) == 1
    scd2_calls = [kind for kind, _ in cur.executed if "valid_to" in kind]
    assert scd2_calls == []


def test_upsert_dim_coin_none_image_url_does_not_overwrite_existing_logo():
    """backfill_market_history.py never has a logo to offer; passing image_url=None must be a
    complete no-op for that column, never blanking out an already-stored logo."""
    cur = _UpsertDimCoinCursor(current_row=(1, "btc", "Bitcoin", "https://img/old.png"))

    coin_key, action = etl.upsert_dim_coin(cur, "bitcoin", "btc", "Bitcoin", image_url=None)

    assert (coin_key, action) == (1, "unchanged")
    update_calls = [kind for kind, _ in cur.executed if kind.startswith("UPDATE dw.dim_coin SET image_url")]
    assert update_calls == []


def test_upsert_dim_coin_scd2_change_carries_forward_existing_image_url_when_none_given():
    cur = _UpsertDimCoinCursor(current_row=(1, "btc", "Old Name", "https://img/old.png"))

    coin_key, action = etl.upsert_dim_coin(cur, "bitcoin", "btc", "New Name", image_url=None)

    assert (coin_key, action) == (999, "updated")
    insert_calls = [p for kind, p in cur.executed if kind.startswith("INSERT INTO dw.dim_coin")]
    assert insert_calls == [("bitcoin", "btc", "New Name", "https://img/old.png")]
    expire_calls = [kind for kind, _ in cur.executed if "valid_to" in kind]
    assert len(expire_calls) == 1


class _IntradayFromStagingCursor:
    def __init__(self, returned_keys: list[int]):
        self.returned_keys = returned_keys
        self.executed: list[tuple[str, tuple | None]] = []

    def execute(self, sql, params=None):
        self.executed.append((_sql_kind(sql), params))

    def fetchall(self):
        return [(k,) for k in self.returned_keys]


def test_insert_intraday_from_staging_returns_rows_inserted():
    cur = _IntradayFromStagingCursor(returned_keys=[10, 11, 12])
    ts = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)

    inserted = etl.insert_intraday_from_staging(cur, run_id=42, observation_timestamp=ts)

    assert inserted == 3
    [(sql, params)] = cur.executed
    assert "INSERT INTO dw.fact_market_intraday" in sql
    assert "ON CONFLICT (coin_key, observation_timestamp) DO NOTHING" in sql
    assert params == (ts, 42, 42)


def test_insert_intraday_from_staging_zero_when_all_conflict():
    cur = _IntradayFromStagingCursor(returned_keys=[])
    ts = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)

    inserted = etl.insert_intraday_from_staging(cur, run_id=42, observation_timestamp=ts)

    assert inserted == 0


# ---------------------------------------------------------------------------
# select_batch: the mechanism that makes a repeated ETL run for the same staged
# batch a safe no-op, and makes "first run on an empty database" return
# cleanly rather than erroring.
# ---------------------------------------------------------------------------


class _SelectBatchCursor:
    def __init__(self, row):
        self.row = row
        self.executed: list[tuple[str, tuple | None]] = []

    def execute(self, sql, params=None):
        self.executed.append((_sql_kind(sql), params))

    def fetchone(self):
        return self.row


def test_select_batch_returns_none_on_empty_database():
    """First run on an empty database: no succeeded staging batch exists at all."""
    cur = _SelectBatchCursor(row=None)

    assert etl.select_batch(cur, run_id=None) is None


def test_select_batch_picks_oldest_unloaded_succeeded_batch():
    cur = _SelectBatchCursor(row=(7,))

    batch_run_id = etl.select_batch(cur, run_id=None)

    assert batch_run_id == 7
    [(sql, params)] = cur.executed
    assert "loaded_at IS NULL" in sql
    assert params == (etl.SOURCE_PIPELINE_NAME,)


def test_select_batch_returns_none_when_the_only_batch_is_already_loaded():
    """Repeated ETL run for a date that's already been loaded: select_batch's auto-pick query
    filters on loaded_at IS NULL, so an already-loaded batch is never picked again -- this is what
    prevents a second `run_etl()` call from re-loading (and duplicating) the same snapshot."""
    cur = _SelectBatchCursor(row=None)  # the query itself excludes loaded_at IS NOT NULL rows

    assert etl.select_batch(cur, run_id=None) is None


def test_select_batch_explicit_run_id_requires_succeeded_status():
    cur = _SelectBatchCursor(row=None)

    with pytest.raises(ValueError, match="not a succeeded"):
        etl.select_batch(cur, run_id=99)


def test_select_batch_explicit_run_id_returns_it_when_valid():
    cur = _SelectBatchCursor(row=(99,))

    assert etl.select_batch(cur, run_id=99) == 99


# ---------------------------------------------------------------------------
# run_etl: overall orchestration -- first run, no-op when nothing to load, and
# rollback-on-failure so a failed load never leaves a partially-loaded batch.
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._one = None
        self._all: list = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        kind = _sql_kind(sql)
        self.conn.executed.append(kind)
        if kind.startswith("SELECT started_at FROM audit.etl_run"):
            self._one = (datetime(2026, 7, 24, tzinfo=timezone.utc),)
        elif kind.startswith("SELECT coin_id, symbol, name, current_price"):
            self._all = self.conn.staged_rows
        elif kind.startswith("UPDATE audit.etl_run SET loaded_at"):
            self.conn.loaded_at_marked = params[0] if params else True

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all


class _FakeConn:
    def __init__(self, staged_rows):
        self.staged_rows = staged_rows
        self.executed: list[str] = []
        self.loaded_at_marked = None
        self.committed = 0
        self.rolled_back = 0

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


def test_run_etl_returns_none_when_nothing_to_load(monkeypatch):
    """Both "first run on an empty database" and "repeated run after everything is already
    loaded" converge on the same outcome: select_batch finds nothing, so run_etl must return None
    without creating any audit.etl_run row or touching any dimension/fact table."""
    monkeypatch.setattr(etl, "select_batch", lambda cur, run_id: None)
    start_calls = []
    monkeypatch.setattr(etl, "start_etl_run", lambda conn: start_calls.append(1))

    conn = _FakeConn(staged_rows=[])

    result = etl.run_etl(conn)

    assert result is None
    assert start_calls == []
    assert conn.committed == 0


def test_run_etl_success_commits_once_and_marks_batch_loaded(monkeypatch):
    monkeypatch.setattr(etl, "select_batch", lambda cur, run_id: 7)
    monkeypatch.setattr(etl, "start_etl_run", lambda conn: 100)
    monkeypatch.setattr(etl, "ensure_dim_date", lambda cur, snapshot_date: True)
    monkeypatch.setattr(etl, "upsert_dim_coin", lambda cur, coin_id, symbol, name, image_url=None: (1, "inserted"))
    monkeypatch.setattr(
        etl, "upsert_fact_market_snapshot", lambda cur, date_key, coin_key, *rest: True
    )
    finish_calls = []
    monkeypatch.setattr(
        etl,
        "finish_etl_run",
        lambda conn, run_id, status, rows_processed, error_message: finish_calls.append(
            (run_id, status, rows_processed, error_message)
        ),
    )

    conn = _FakeConn(staged_rows=[("bitcoin", "btc", "Bitcoin", 65000.0, None, None, None, None, None)])

    result = etl.run_etl(conn)

    assert result.etl_run_id == 100
    assert result.staging_run_id == 7
    assert result.fact_inserted == 1
    assert result.snapshot_date == date(2026, 7, 24)
    assert conn.committed == 1
    assert conn.rolled_back == 0
    assert conn.loaded_at_marked
    assert finish_calls == [(100, "succeeded", 1, None)]


def test_run_etl_rolls_back_and_records_failure_without_marking_batch_loaded(monkeypatch):
    """A failure partway through the batch must not leave a misleading partial load: the
    transaction rolls back (undoing any fact/dimension writes and the loaded_at stamp), and the
    failure is recorded on audit.etl_run so the batch remains eligible for a future retry."""
    monkeypatch.setattr(etl, "select_batch", lambda cur, run_id: 7)
    monkeypatch.setattr(etl, "start_etl_run", lambda conn: 100)
    monkeypatch.setattr(etl, "ensure_dim_date", lambda cur, snapshot_date: True)

    def _raise(cur, coin_id, symbol, name, image_url=None):
        raise RuntimeError("dim_coin upsert failed")

    monkeypatch.setattr(etl, "upsert_dim_coin", _raise)

    finish_calls = []
    monkeypatch.setattr(
        etl,
        "finish_etl_run",
        lambda conn, run_id, status, rows_processed, error_message: finish_calls.append(
            (run_id, status, rows_processed, error_message)
        ),
    )

    conn = _FakeConn(staged_rows=[("bitcoin", "btc", "Bitcoin", 65000.0, None, None, None, None, None)])

    with pytest.raises(etl.ETLError):
        etl.run_etl(conn)

    assert conn.committed == 0
    assert conn.rolled_back == 1
    assert conn.loaded_at_marked is None
    assert finish_calls == [(100, "failed", 0, "dim_coin upsert failed")]

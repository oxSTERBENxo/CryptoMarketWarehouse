from database import bootstrap_db


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._one = None
        self._all: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        self.conn.executed.append(text)

        if "to_regclass" in text:
            self._one = (self.conn.already_migrated,)
        elif text.startswith("SELECT filename FROM public.schema_migrations"):
            self._all = [(f,) for f in sorted(self.conn.ledger)]
        elif text.startswith("INSERT INTO public.schema_migrations"):
            self.conn.ledger.add(params[0])
        elif text.startswith("CREATE TABLE IF NOT EXISTS public.schema_migrations"):
            pass
        elif "FAIL_ME" in text:
            raise RuntimeError("simulated migration failure")
        else:
            self.conn.ran_sql.append(text)

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all


class _FakeConn:
    def __init__(self, already_migrated: bool = False, initial_ledger=None):
        self.already_migrated = already_migrated
        self.ledger: set[str] = set(initial_ledger or [])
        self.executed: list[str] = []
        self.ran_sql: list[str] = []
        self.committed = 0
        self.rolled_back = 0

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


def _write_script(directory, name, content="-- test migration\n"):
    path = directory / name
    path.write_text(content)
    return path


def test_fresh_database_runs_every_script_once(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap_db, "DB_DIR", tmp_path)
    _write_script(tmp_path, "001_a.sql")
    _write_script(tmp_path, "002_b.sql")
    scripts = bootstrap_db.discover_scripts()

    conn = _FakeConn(already_migrated=False)
    result = bootstrap_db.run_bootstrap(conn, scripts, verbose=False)

    assert result.ok
    assert result.ran == ["001_a.sql", "002_b.sql"]
    assert result.skipped == []
    assert result.backfilled == []
    assert conn.ledger == {"001_a.sql", "002_b.sql"}


def test_repeated_bootstrap_run_is_a_no_op(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap_db, "DB_DIR", tmp_path)
    _write_script(tmp_path, "001_a.sql")
    conn = _FakeConn(already_migrated=False)
    bootstrap_db.run_bootstrap(conn, bootstrap_db.discover_scripts(), verbose=False)

    result = bootstrap_db.run_bootstrap(conn, bootstrap_db.discover_scripts(), verbose=False)

    assert result.ok
    assert result.ran == []
    assert result.skipped == ["001_a.sql"]


def test_new_migration_after_previous_bootstrap_only_runs_the_new_file(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap_db, "DB_DIR", tmp_path)
    _write_script(tmp_path, "001_a.sql")
    conn = _FakeConn(already_migrated=False)
    bootstrap_db.run_bootstrap(conn, bootstrap_db.discover_scripts(), verbose=False)

    _write_script(tmp_path, "002_b.sql")
    result = bootstrap_db.run_bootstrap(conn, bootstrap_db.discover_scripts(), verbose=False)

    assert result.ran == ["002_b.sql"]
    assert result.skipped == ["001_a.sql"]


def test_legacy_database_backfills_pre_cutoff_scripts_without_replaying_them(tmp_path, monkeypatch):
    """Reproduces the real bug this ledger fixes: a database bootstrapped before the ledger
    existed (dw.dim_coin already present, ledger empty) must not replay old
    CREATE OR REPLACE VIEW-style migrations that later files have since widened -- Postgres
    rejects narrowing a view's columns ("cannot drop columns from view"). Such files must be
    backfilled as already-applied instead, and only genuinely new files should run."""
    monkeypatch.setattr(bootstrap_db, "DB_DIR", tmp_path)
    monkeypatch.setattr(bootstrap_db, "LEGACY_CUTOFF", 2)
    _write_script(tmp_path, "001_a.sql")
    _write_script(tmp_path, "002_b.sql")
    _write_script(tmp_path, "003_c.sql")

    conn = _FakeConn(already_migrated=True)
    result = bootstrap_db.run_bootstrap(conn, bootstrap_db.discover_scripts(), verbose=False)

    assert result.ok
    assert result.backfilled == ["001_a.sql", "002_b.sql"]
    assert result.ran == ["003_c.sql"]
    assert conn.ran_sql == ["-- test migration"]
    assert conn.ledger == {"001_a.sql", "002_b.sql", "003_c.sql"}


def test_failure_stops_bootstrap_and_leaves_failed_file_unmarked(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap_db, "DB_DIR", tmp_path)
    _write_script(tmp_path, "001_a.sql")
    _write_script(tmp_path, "002_bad.sql", content="FAIL_ME")
    _write_script(tmp_path, "003_c.sql")

    conn = _FakeConn(already_migrated=False)
    result = bootstrap_db.run_bootstrap(conn, bootstrap_db.discover_scripts(), verbose=False)

    assert not result.ok
    assert result.failed == "002_bad.sql"
    assert result.ran == ["001_a.sql"]
    assert "002_bad.sql" not in conn.ledger
    assert "003_c.sql" not in conn.ledger
    assert conn.rolled_back == 1

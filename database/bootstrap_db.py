import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from database import get_connection

DB_DIR = Path(__file__).parent.parent / "db"

# Highest migration number that existed before public.schema_migrations (the applied-migrations
# ledger) was introduced. Before the ledger, bootstrap_db.py replayed every *.sql file on every
# run; several analytics views were widened over time via CREATE OR REPLACE VIEW (e.g.
# 008_latest_snapshot.sql -> 019_latest_snapshot_per_coin.sql -> 027_views_add_image_url.sql), and
# Postgres refuses to CREATE OR REPLACE a view with fewer columns than it currently has ("cannot
# drop columns from view") -- so replaying the whole set against an already-migrated database
# failed at the first superseded file. The very first ledger-aware run backfills every file
# numbered <= LEGACY_CUTOFF as already-applied (without re-running it) whenever the database
# already looks migrated, instead of hitting that failure.
LEGACY_CUTOFF = 28


def discover_scripts() -> list[Path]:
    return sorted(
        DB_DIR.rglob("*.sql"),
        key=lambda p: int(re.match(r"(\d+)_", p.name).group(1)),
    )


def _script_number(path: Path) -> int:
    return int(re.match(r"(\d+)_", path.name).group(1))


def _rel_name(path: Path) -> str:
    return path.relative_to(DB_DIR).as_posix()


def _ensure_ledger_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS public.schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    conn.commit()


def _applied_filenames(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM public.schema_migrations")
        return {row[0] for row in cur.fetchall()}


def _mark_applied(conn, filename: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.schema_migrations (filename) VALUES (%s) ON CONFLICT DO NOTHING",
            (filename,),
        )
    conn.commit()


def _looks_already_migrated(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('dw.dim_coin') IS NOT NULL")
        return bool(cur.fetchone()[0])


@dataclass
class BootstrapResult:
    ran: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    backfilled: list[str] = field(default_factory=list)
    failed: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.failed is None


def run_bootstrap(conn, scripts: list[Path], *, verbose: bool = True) -> BootstrapResult:
    """Apply every not-yet-applied migration file, tracked in `public.schema_migrations`, so
    bootstrap is safe to re-run against an already-migrated database. See LEGACY_CUTOFF for the
    one-time backfill of databases that predate the ledger."""
    result = BootstrapResult()
    _ensure_ledger_table(conn)
    applied = _applied_filenames(conn)

    if not applied and _looks_already_migrated(conn):
        for path in scripts:
            if _script_number(path) <= LEGACY_CUTOFF:
                rel = _rel_name(path)
                _mark_applied(conn, rel)
                result.backfilled.append(rel)
        applied = _applied_filenames(conn)
        if verbose and result.backfilled:
            print(
                f"Detected an already-migrated database predating the migration ledger; "
                f"backfilled {len(result.backfilled)} legacy migration(s) as applied without re-running them."
            )

    for path in scripts:
        rel = _rel_name(path)
        if rel in applied:
            result.skipped.append(rel)
            continue

        if verbose:
            print(f"Running {rel} ...", end=" ", flush=True)
        try:
            with conn.cursor() as cur:
                cur.execute(path.read_text())
            conn.commit()
        except Exception as exc:
            conn.rollback()
            result.failed = rel
            result.error = str(exc)
            if verbose:
                print("FAILED")
                print(f"  {exc}")
                print(f"Bootstrap failed at {rel}")
            return result

        _mark_applied(conn, rel)
        applied.add(rel)
        result.ran.append(rel)
        if verbose:
            print("OK")

    return result


def main() -> int:
    scripts = discover_scripts()
    if not scripts:
        print(f"No SQL scripts found under {DB_DIR}")
        return 1

    conn = get_connection()
    try:
        result = run_bootstrap(conn, scripts)
    finally:
        conn.close()

    if not result.ok:
        return 1

    if result.ran:
        print(f"Bootstrap completed successfully ({len(result.ran)} migration(s) applied).")
    else:
        print("Bootstrap completed successfully (no new migrations to apply).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

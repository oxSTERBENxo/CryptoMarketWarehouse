import re
import sys
from pathlib import Path

from database import get_connection

DB_DIR = Path(__file__).parent / "db"


def discover_scripts() -> list[Path]:
    return sorted(
        DB_DIR.rglob("*.sql"),
        key=lambda p: int(re.match(r"(\d+)_", p.name).group(1)),
    )


def main() -> int:
    scripts = discover_scripts()
    if not scripts:
        print(f"No SQL scripts found under {DB_DIR}")
        return 1

    conn = get_connection()
    try:
        for path in scripts:
            rel = path.relative_to(DB_DIR)
            print(f"Running {rel} ...", end=" ", flush=True)
            try:
                with conn.cursor() as cur:
                    cur.execute(path.read_text())
                conn.commit()
            except Exception as exc:
                conn.rollback()
                print("FAILED")
                print(f"  {exc}")
                print(f"Bootstrap failed at {rel}")
                return 1
            print("OK")
    finally:
        conn.close()

    print("Bootstrap completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

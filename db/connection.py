"""
Connection + transaction helpers.

Every tool that mutates stock (finalize_bill, receive_stock, khata settlement) must run
inside `transaction()` so a sale and a stock-in in flight at the same time can't corrupt
quantity. SQLite: BEGIN IMMEDIATE takes a write lock up front instead of on first write,
which is what avoids the classic "two readers upgrade to writers" race.
For Postgres, swap the `BEGIN IMMEDIATE` for `SELECT ... FOR UPDATE` on the row(s) touched.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "store.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _resolve_db_path() -> Path:
    """KIRANA_DB_PATH lets tests (and alternate deployments) point at a different
    file without touching the real store.db."""
    override = os.environ.get("KIRANA_DB_PATH")
    return Path(override) if override else DEFAULT_DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(
        _resolve_db_path(),
        isolation_level=None
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    conn = get_connection()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Take a write lock immediately, so concurrent stock mutations serialize cleanly."""
    conn.execute("BEGIN IMMEDIATE;")
    try:
        yield conn
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise
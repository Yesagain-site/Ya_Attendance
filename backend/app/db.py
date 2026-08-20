"""Postgres access — a tiny pooled helper, no ORM."""
import os
import time

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

DATABASE_URL = os.environ["DATABASE_URL"]

# Canonical full-name expression (assumes the employees table is aliased `e`).
# Prefers first+last (from BioTime), falls back to the device short name, then PIN.
# Device ADMS pushes only overwrite `e.name`, never first/last, so this stays full.
FULLNAME = ("COALESCE(NULLIF(TRIM(COALESCE(e.first_name,'')||' '||"
            "COALESCE(e.last_name,'')),''), e.name, e.pin)")

_pool: SimpleConnectionPool | None = None


def init_pool(retries: int = 20, delay: float = 2.0) -> None:
    """Create the pool, waiting for Postgres to accept connections."""
    global _pool
    last_err = None
    for _ in range(retries):
        try:
            _pool = SimpleConnectionPool(1, 8, dsn=DATABASE_URL)
            # Sanity check one connection.
            conn = _pool.getconn()
            _pool.putconn(conn)
            return
        except Exception as e:  # pragma: no cover - startup race
            last_err = e
            time.sleep(delay)
    raise RuntimeError(f"Could not connect to Postgres: {last_err}")


def _get():
    if _pool is None:
        init_pool()
    return _pool.getconn()


def _put(conn):
    if _pool is not None:
        _pool.putconn(conn)


def query(sql: str, params=None):
    """Run a SELECT, return list[dict]."""
    conn = _get()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
        conn.commit()
        return [dict(r) for r in rows]
    finally:
        _put(conn)


def execute(sql: str, params=None):
    """Run an INSERT/UPDATE/DELETE, return affected row count."""
    conn = _get()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            n = cur.rowcount
        conn.commit()
        return n
    finally:
        _put(conn)


def executemany_returning_new(sql: str, rows: list[tuple]) -> int:
    """
    Run many inserts (each with ON CONFLICT DO NOTHING) and return how many
    were actually inserted (i.e. not duplicates).
    """
    if not rows:
        return 0
    conn = _get()
    inserted = 0
    try:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(sql, r)
                inserted += cur.rowcount  # 1 if inserted, 0 if conflict
        conn.commit()
        return inserted
    finally:
        _put(conn)

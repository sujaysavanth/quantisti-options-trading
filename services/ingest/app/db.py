"""Postgres access for the gap detector (raw SQL, no ORM, like the other services).

Scans run at most every couple of minutes, so a fresh connection per scan is simpler
than a pool and never holds a connection between scans.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional


@contextmanager
def connect(url: str) -> Iterator["psycopg2.extensions.connection"]:
    """A connection that commits on success and rolls back on error."""
    import psycopg2
    conn = psycopg2.connect(url, connect_timeout=5)
    try:
        with conn:                       # psycopg2: commit/rollback, does not close
            yield conn
    finally:
        conn.close()


def ping(url: str) -> Optional[str]:
    """None if Postgres answers, else the error text."""
    try:
        with connect(url) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return None
    except Exception as exc:
        return str(exc).strip()

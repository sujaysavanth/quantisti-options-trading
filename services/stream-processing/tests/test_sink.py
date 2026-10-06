"""Sink tests against the real Postgres, inside a transaction that is always rolled back."""

import os
from datetime import date, datetime, timedelta, timezone

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from jobs.sink import write_chain, write_daily  # noqa: E402

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quantisti:quantisti@postgres:5432/quantisti")
DAY = date(2099, 1, 5)          # far from real data, and rolled back anyway
QUOTED = datetime(2099, 1, 5, 21, 0)


@pytest.fixture
def conn():
    try:
        c = psycopg2.connect(DATABASE_URL, connect_timeout=3)
    except psycopg2.OperationalError:
        pytest.skip("Postgres not reachable")
    yield c
    c.rollback()
    c.close()


def chain_row(bid, quoted_at=QUOTED, strike=7775.0):
    return ("SPX", DAY, date(2099, 1, 9), strike, "C", 7773.95, bid, bid + 0.4, None, 100, 5, 0.11, 0.5, quoted_at, "test")


def snapshot(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT strike, bid, quoted_at FROM option_chain_snapshots WHERE source = 'test' ORDER BY strike")
        return cur.fetchall()


def test_chain_upsert_is_idempotent(conn):
    rows = [chain_row(40.5), chain_row(30.0, strike=7780.0)]
    write_chain(conn, rows)
    first = snapshot(conn)
    write_chain(conn, rows)                                    # a replayed micro-batch
    assert snapshot(conn) == first and len(first) == 2
    assert first[0][2] == QUOTED.replace(tzinfo=timezone.utc)  # naive Spark timestamp stored as UTC


def test_older_quote_never_overwrites_newer(conn):
    write_chain(conn, [chain_row(40.5)])
    write_chain(conn, [chain_row(10.0, quoted_at=QUOTED - timedelta(hours=1))])
    assert float(snapshot(conn)[0][1]) == 40.5
    write_chain(conn, [chain_row(41.0, quoted_at=QUOTED + timedelta(minutes=2))])
    assert float(snapshot(conn)[0][1]) == 41.0


def test_daily_upserts_and_recomputes_hv(conn):
    start = date(2099, 1, 1)
    days = [start + timedelta(days=i) for i in range(40)]
    closes = [100 * (1.01 if i % 2 else 0.99) ** i for i in range(40)]
    underlying = [("TEST", d, c, c, c, c, 0) for d, c in zip(days, closes)]
    write_daily(conn, underlying, [(DAY, 16.4)], [(DAY, 0.0412)])
    write_daily(conn, underlying, [(DAY, 16.4)], [(DAY, 0.0412)])   # idempotent
    with conn.cursor() as cur:
        cur.execute("SELECT count(*), count(historical_volatility) FROM underlying_daily WHERE symbol = 'TEST'")
        assert cur.fetchone() == (40, 10)          # only days with 30 returns behind them get an HV
        cur.execute("SELECT close FROM vix_daily WHERE date = %s", (DAY,))
        assert float(cur.fetchone()[0]) == 16.4
        cur.execute("SELECT rate FROM rates_daily WHERE date = %s", (DAY,))
        assert float(cur.fetchone()[0]) == 0.0412

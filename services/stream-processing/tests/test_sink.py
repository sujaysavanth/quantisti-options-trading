"""Sink tests against the real Postgres, inside a transaction that is always rolled back."""

import os
from datetime import date, datetime, timedelta, timezone

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from jobs.sink import copy_chain, write_bars, write_chain, write_daily  # noqa: E402

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


def chain_row(bid, quoted_at=QUOTED, strike=7775.0, oi=100, volume=5):
    ask = None if bid is None else bid + 0.4
    return ("SPX", DAY, date(2099, 1, 9), strike, "C", 7773.95, bid, ask, None, oi, volume, 0.11, 0.5, quoted_at, "test")


def snapshot(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT strike, bid, quoted_at FROM option_chain_snapshots WHERE source = 'test' ORDER BY strike")
        return cur.fetchall()


def quote_and_counts(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT bid, ask, quoted_at, open_interest, volume FROM option_chain_snapshots WHERE source = 'test'")
        bid, ask, quoted_at, oi, volume = cur.fetchone()
        return (float(bid) if bid is not None else None, float(ask) if ask is not None else None,
                quoted_at.replace(tzinfo=None), oi, volume)


@pytest.mark.parametrize("write", [write_chain, copy_chain])
def test_quote_less_capture_keeps_the_quote_but_updates_counts(conn, write):
    write(conn, [chain_row(40.5, oi=1200, volume=900)])
    write(conn, [chain_row(None, quoted_at=QUOTED + timedelta(minutes=30), oi=1250, volume=1500)])  # CBOE's empty capture
    assert quote_and_counts(conn) == (40.5, 40.9, QUOTED, 1250, 1500)
    write(conn, [chain_row(41.0, quoted_at=QUOTED + timedelta(minutes=40), oi=1260, volume=1600)])  # a real quote again
    assert quote_and_counts(conn) == (41.0, 41.4, QUOTED + timedelta(minutes=40), 1260, 1600)


def test_quote_less_capture_replaces_a_quote_less_one(conn):
    write_chain(conn, [chain_row(None, oi=10)])
    write_chain(conn, [chain_row(None, quoted_at=QUOTED + timedelta(minutes=5), oi=20)])
    assert quote_and_counts(conn) == (None, None, QUOTED + timedelta(minutes=5), 20, 5)


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


def five_minute(conn, ts):
    with conn.cursor() as cur:
        cur.execute("SELECT volume, source FROM intraday_bars WHERE symbol = 'SPX' AND interval = '5m' AND ts = %s",
                    (ts.replace(tzinfo=timezone.utc),))
        return cur.fetchone()


def test_vendor_bar_beats_our_aggregate(conn):
    ts = datetime(2099, 1, 6, 14, 30)
    write_bars(conn, [("SPX", "5m", ts, 100.0, 101.0, 99.0, 100.5, 40, "agg_1m")])     # missed a minute
    write_bars(conn, [("SPX", "5m", ts, 100.0, 101.0, 99.0, 100.5, 50, "yahoo")])      # backfill: vendor wins
    assert five_minute(conn, ts) == (50, "yahoo")
    write_bars(conn, [("SPX", "5m", ts, 100.0, 101.0, 99.0, 100.5, 45, "agg_1m")])     # aggregate can't undo it
    assert five_minute(conn, ts) == (50, "yahoo")


def test_bars_upsert_and_partial_window_overwrite(conn):
    ts = datetime(2099, 1, 5, 14, 30)
    one_minute = [("SPX", "1m", ts + timedelta(minutes=m), 100.0, 101.0, 99.0, 100.5, 10, "yahoo") for m in range(3)]
    write_bars(conn, one_minute)
    write_bars(conn, one_minute)                                          # replay: no change
    write_bars(conn, [("SPX", "5m", ts, 100.0, 101.0, 99.0, 100.5, 30, "agg_1m")])     # window so far
    write_bars(conn, [("SPX", "5m", ts, 100.0, 102.0, 98.0, 101.0, 50, "agg_1m")])     # same window, complete
    with conn.cursor() as cur:
        cur.execute("SELECT interval, count(*), max(volume), min(source) FROM intraday_bars "
                    "WHERE symbol = 'SPX' AND ts >= %s AND ts < %s GROUP BY interval ORDER BY interval",
                    (ts.replace(tzinfo=timezone.utc), (ts + timedelta(hours=1)).replace(tzinfo=timezone.utc)))
        assert cur.fetchall() == [("1m", 3, 10, "yahoo"), ("5m", 1, 50, "agg_1m")]


def test_copy_chain_matches_the_row_upsert(conn):
    rows = [chain_row(40.5), chain_row(30.0, strike=7780.0)]
    assert copy_chain(conn, rows) == 2
    assert copy_chain(conn, rows) == 2                                    # re-import: same rows, no duplicates
    assert [(float(s), float(b)) for s, b, _ in snapshot(conn)] == [(7775.0, 40.5), (7780.0, 30.0)]
    copy_chain(conn, [chain_row(10.0, quoted_at=QUOTED - timedelta(days=1))])   # older capture: ignored
    assert float(snapshot(conn)[0][1]) == 40.5
    assert copy_chain(conn, []) == 0

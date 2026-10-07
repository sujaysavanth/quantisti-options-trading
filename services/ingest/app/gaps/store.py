"""SQL for the gap detector: what's stored (coverage), and the ingest_gaps table.

ingest_gaps.status:
    requested      a backfill has been (or is about to be) requested
    filled         the data is now in the table (set by a later check, never at publish time)
    unrecoverable  no source can supply it, or MAX_ATTEMPTS backfills didn't bring it back
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import List, Optional

from psycopg2.extras import RealDictCursor, execute_values

from .. import market_spec
from .detector import Coverage, Gap
from .expected import min_bars


def load_coverage(conn, now: datetime) -> Coverage:
    cov = Coverage()
    with conn.cursor() as cur:
        cur.execute("SELECT date FROM underlying_daily WHERE symbol = 'SPX'")
        cov.daily = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT date FROM vix_daily")
        cov.vix = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT date FROM rates_daily")
        cov.rates = {r[0] for r in cur.fetchall()}

        # Bars per ET session date. Only Yahoo's longest window (1h, ~730 days) matters.
        cur.execute("""
            SELECT symbol, interval, (ts AT TIME ZONE 'America/New_York')::date AS d, count(*)
              FROM intraday_bars
             WHERE ts >= %s
             GROUP BY 1, 2, 3""", (now - timedelta(days=740),))
        for symbol, interval, d, n in cur.fetchall():
            cov.bars.setdefault((symbol, interval), {})[d] = n

        cur.execute("""
            SELECT snapshot_date, bool_and(source = 'optionsdx')
              FROM option_chain_snapshots WHERE symbol = 'SPX' GROUP BY 1""")
        rows = cur.fetchall()
        cov.chain = {d for d, _ in rows}
        live = [d for d, only_optionsdx in rows if not only_optionsdx]
        cov.collection_start = min(live) if live else None
    return cov


def collection_start(conn) -> Optional[date]:
    """First chain session with live (non-OptionsDX) quotes."""
    with conn.cursor() as cur:
        cur.execute("SELECT min(snapshot_date) FROM option_chain_snapshots"
                    " WHERE symbol = 'SPX' AND source <> 'optionsdx' AND snapshot_date > '2023-12-31'")
        return cur.fetchone()[0]


def is_present(conn, dataset: str, symbol: str, day: date) -> bool:
    """Whether the data for one gap has arrived (for intraday: enough bars)."""
    with conn.cursor() as cur:
        if dataset == "daily":
            cur.execute("SELECT 1 FROM underlying_daily WHERE symbol = %s AND date = %s", (symbol, day))
        elif dataset == "vix":
            cur.execute("SELECT 1 FROM vix_daily WHERE date = %s", (day,))
        elif dataset == "rates":
            cur.execute("SELECT 1 FROM rates_daily WHERE date = %s", (day,))
        elif dataset == "chain":
            cur.execute("SELECT 1 FROM option_chain_snapshots WHERE symbol = %s AND snapshot_date = %s LIMIT 1",
                        (symbol, day))
        elif dataset == "intraday":
            sym, _, interval = symbol.partition(":")
            start = datetime.combine(day, time(0), market_spec.TZ)
            cur.execute("SELECT count(*) FROM intraday_bars WHERE symbol = %s AND interval = %s AND ts >= %s AND ts < %s",
                        (sym, interval, start, start + timedelta(days=1)))
            return cur.fetchone()[0] >= min_bars(day, interval)
        else:
            raise ValueError(f"unknown dataset {dataset!r}")
        return cur.fetchone() is not None


def upsert_gaps(conn, gaps: List[Gap]) -> List[dict]:
    """Record gaps; returns every row touched with its current status and attempts.

    A gap seen again keeps its status, attempts and detail (the worker may have noted an error there).
    A gap that was `filled` and is missing again starts over as `requested` with 0 attempts.
    """
    if not gaps:
        return []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        return execute_values(cur, """
            INSERT INTO ingest_gaps (dataset, symbol, gap_date, detail) VALUES %s
            ON CONFLICT (dataset, symbol, gap_date) DO UPDATE SET
                status     = CASE WHEN ingest_gaps.status = 'filled' THEN 'requested' ELSE ingest_gaps.status END,
                attempts   = CASE WHEN ingest_gaps.status = 'filled' THEN 0 ELSE ingest_gaps.attempts END,
                detail     = CASE WHEN ingest_gaps.status = 'filled' THEN EXCLUDED.detail ELSE ingest_gaps.detail END,
                updated_at = now()
            RETURNING dataset, symbol, gap_date, status, attempts, detail""",
            [(g.dataset, g.symbol, g.gap_date, g.detail) for g in gaps], fetch=True)


def open_gaps(conn) -> List[dict]:
    """Gaps whose data might still turn up (`unrecoverable` too: someone may load it by hand)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT dataset, symbol, gap_date FROM ingest_gaps WHERE status IN ('requested', 'unrecoverable')")
        return cur.fetchall()


def set_status(conn, dataset: str, symbol: str, day: date, status: str, detail: Optional[str] = None) -> None:
    with conn.cursor() as cur:
        cur.execute("""UPDATE ingest_gaps SET status = %s, detail = COALESCE(%s, detail), updated_at = now()
                        WHERE dataset = %s AND symbol = %s AND gap_date = %s""",
                    (status, detail, dataset, symbol, day))


def set_attempts(conn, dataset: str, symbol: str, day: date, attempts: int) -> None:
    with conn.cursor() as cur:
        cur.execute("""UPDATE ingest_gaps SET attempts = %s, updated_at = now()
                        WHERE dataset = %s AND symbol = %s AND gap_date = %s""", (attempts, dataset, symbol, day))


def list_gaps(conn, status: Optional[str] = None, dataset: Optional[str] = None, limit: int = 500) -> List[dict]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT dataset, symbol, gap_date, status, attempts, detail, first_seen, updated_at
              FROM ingest_gaps
             WHERE (%(status)s::text IS NULL OR status = %(status)s)
               AND (%(dataset)s::text IS NULL OR dataset = %(dataset)s)
             ORDER BY gap_date DESC, dataset, symbol
             LIMIT %(limit)s""", {"status": status, "dataset": dataset, "limit": limit})
        return cur.fetchall()


def count_gaps(conn) -> List[dict]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT dataset, status, count(*) AS gaps FROM ingest_gaps GROUP BY 1, 2 ORDER BY 1, 2")
        return cur.fetchall()

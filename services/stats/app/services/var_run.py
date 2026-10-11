"""Compute the open book's VaR by every method (var.py), store it once per session after the close, and pair stored
VaR with the realised next-session P&L from the portfolio's close snapshots."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np
from psycopg2.extras import Json

from .. import market_spec
from ..db.connection import get_db_connection, return_db_connection
from . import stress as st
from . import var
from .exposure import Market
from .pricing import greeks

logger = logging.getLogger(__name__)

CLOSE_DELAY = timedelta(minutes=20)        # same window as the portfolio's close snapshot
OVERNIGHT_OPEN = time(20, 15)


def _revalue_all(legs, n_trades: int, rate: float, moves: Sequence[var.Move]) -> List[float]:
    return [st.revalue(legs, n_trades, rate, st.Scenario("", r, dv, 1))[0] for r, dv in moves]


def book_totals(legs: Sequence[st.PricedLeg], rate: float) -> Dict[str, float]:
    """Dollar Greeks of the priced legs (same units as exposure.portfolio_greeks)."""
    t = {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0}
    for leg in legs:
        if leg.inputs is None:
            continue
        x = leg.inputs
        g = greeks(x.spot, leg.strike, x.T, rate, x.iv, market_spec.DIVIDEND_YIELD, leg.option_type)
        size = leg.signed_qty * st.MULTIPLIER
        for k in t:
            t[k] += getattr(g, k) * size
    return t


def compute(trades: Sequence[Mapping[str, Any]], market: Market, rate: float, moves: Sequence[var.Move],
            sigma_now: Optional[float], sigma_origin: Optional[str]) -> Dict[str, Any]:
    legs, unpriced = st.book(trades, market)
    methods: Dict[str, Any] = {}
    if moves:
        methods["historical"] = var.summarise(_revalue_all(legs, len(trades), rate, moves),
                                              {"lookback_sessions": len(moves)})
        filtered, sig, source = var.filtered_moves(moves, sigma_now)
        methods["filtered_historical"] = var.summarise(
            _revalue_all(legs, len(trades), rate, filtered),
            {"sigma_now": sig, "sigma_source": source, "garch_origin": sigma_origin if source == "garch" else None,
             "sigma_long_run": float(np.std([m[0] for m in moves]))})
        recent = moves[-var.LOOKBACK:]
        totals = book_totals(legs, rate)
        methods["delta_gamma_vega"] = var.summarise(
            var.taylor_pnl(totals, market.spot, recent) if len(recent) > 2 else [],
            {"lookback_sessions": len(recent), "greeks": totals})
    return {"spot": market.spot, "rate": rate, "quoted_at": market.quoted_at, "open_trades": len(trades),
            "methods": methods, "unpriced": unpriced}


def due_close(now: datetime) -> Optional[date]:
    """The session whose VaR should be stored now: CLOSE_DELAY after its close until 20:15 ET, else None."""
    day = now.astimezone(market_spec.TZ).date()
    if not market_spec.is_trading_day(day):
        return None
    starts = market_spec.session_close(day) + CLOSE_DELAY
    ends = datetime.combine(day, OVERNIGHT_OPEN, market_spec.TZ).astimezone(timezone.utc)
    return day if starts <= now < ends else None


def rows_for(session: date, result: Mapping[str, Any], account_value: Optional[float]) -> List[Dict[str, Any]]:
    rows = []
    for method, m in result["methods"].items():
        details = {k: v for k, v in m.items() if k != "levels"}
        for c, level in m["levels"].items():
            rows.append({"session": session, "method": method, "confidence": float(c), "var": level["var"],
                         "es": level["es"], "account_value": account_value, "open_trades": result["open_trades"],
                         "details": details})
    return rows


def realised_next(closes: Sequence[Mapping[str, Any]]) -> Dict[date, float]:
    """session -> account value change to the next session's close snapshot (only when that is the next session)."""
    pts = sorted((date.fromisoformat(str(c["session"])), float(c["account_value"])) for c in closes)
    out = {}
    for (d0, v0), (d1, v1) in zip(pts, pts[1:]):
        nxt = market_spec.trading_days(d0 + timedelta(days=1), d0 + timedelta(days=10))
        if nxt and nxt[0] == d1:
            out[d0] = v1 - v0
    return out


class VarStore:
    COLUMNS = ("session", "method", "confidence", "var", "es", "account_value", "open_trades", "details")

    def exists(self, session: date) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM risk_var WHERE session = %s LIMIT 1", (session,))
                return cur.fetchone() is not None
        finally:
            return_db_connection(conn)

    def save(self, rows: Sequence[Mapping[str, Any]]) -> int:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                n = 0
                for r in rows:
                    cur.execute(
                        f"INSERT INTO risk_var ({', '.join(self.COLUMNS)}) VALUES ({', '.join(['%s'] * len(self.COLUMNS))}) "
                        "ON CONFLICT (session, method, confidence) DO NOTHING",
                        [Json(r[c]) if c == "details" else r[c] for c in self.COLUMNS])
                    n += cur.rowcount
            conn.commit()
            return n
        except Exception:
            conn.rollback()
            raise
        finally:
            return_db_connection(conn)

    def list(self, start: Optional[date] = None, end: Optional[date] = None) -> List[Dict[str, Any]]:
        sql, args = "SELECT session, method, confidence, var, es, account_value, open_trades, details FROM risk_var", []
        where = []
        if start:
            where.append("session >= %s")
            args.append(start)
        if end:
            where.append("session <= %s")
            args.append(end)
        if where:
            sql += " WHERE " + " AND ".join(where)
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql + " ORDER BY session, method, confidence", args)
                rows = cur.fetchall()
        finally:
            return_db_connection(conn)
        num = {"confidence", "var", "es", "account_value"}
        return [{k: (float(v) if k in num and v is not None else v) for k, v in dict(r).items()} for r in rows]


async def current() -> Optional[Dict[str, Any]]:
    """The open book's VaR now, from live inputs; None if the simulator or the quote is unavailable."""
    from .. import clients        # here, not at import: keeps the pure functions above testable without httpx calls
    trades, account = await clients.open_trades(), await clients.account()
    quote = await clients.quote()
    if trades is None or account is None or not quote or not quote.get("last_price"):
        return None
    rate = clients.latest_rate()
    rate = rate if rate is not None else market_spec.FALLBACK_RATE
    garch = await clients.garch_next_sigma()
    result = compute(trades, Market(quote, rate), rate, clients.daily_moves() or [],
                     garch[0] if garch else None, garch[1] if garch else None)
    result["account_value"] = float(account["account_value"])
    return result


async def store_due(store: VarStore, now: Optional[datetime] = None) -> int:
    """Store the session's VaR if it is due and not stored yet. Returns rows written."""
    session = due_close(now or datetime.now(timezone.utc))
    if session is None or store.exists(session):
        return 0
    result = await current()
    if result is None or not result["methods"]:
        return 0
    n = store.save(rows_for(session, result, result["account_value"]))
    logger.info("stored %d VaR rows for %s", n, session)
    return n

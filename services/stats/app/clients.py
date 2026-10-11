"""HTTP clients for the portfolio service (net positions), the simulator (open trades, account, capital rules) and
market-stream (live SPX quote), ml (GARCH next-session volatility), plus reads from Postgres (latest T-bill rate,
SPX / VIX daily moves). Each returns None
when its source is unavailable."""

import logging
from typing import Any, Optional

import httpx

from .config import get_settings
from .db.connection import get_db_connection, return_db_connection

logger = logging.getLogger(__name__)


async def _get(url: str) -> Optional[Any]:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=15.0)
            response.raise_for_status()
            return response.json()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("GET %s failed: %s", url, exc)
        return None


async def _post(url: str, body: dict) -> Optional[Any]:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=body, timeout=30.0)
            response.raise_for_status()
            return response.json()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("POST %s failed: %s", url, exc)
        return None


def _simulator(path: str) -> str:
    return f"{get_settings().SIMULATOR_URL.rstrip('/')}{path}"


async def open_trades() -> Optional[list]:
    trades = await _get(_simulator("/v1/paper/orders"))
    return None if trades is None else [t for t in trades if t["status"] == "open"]


async def account() -> Optional[dict]:
    return await _get(_simulator("/v1/paper/account"))


async def capital_scenarios(body: dict) -> Optional[list]:
    """The simulator's capital per scenario: {capital_held, by_trade: [{amount, basis}]}."""
    out = await _post(_simulator("/v1/paper/capital-held"), body)
    return None if out is None else out["scenarios"]


async def capital_held(body: dict) -> Optional[list]:
    """Total capital held per scenario, from the simulator's rules."""
    out = await capital_scenarios(body)
    return None if out is None else [s["capital_held"] for s in out]


async def positions() -> Optional[list]:
    body = await _get(f"{get_settings().PORTFOLIO_URL.rstrip('/')}/v1/portfolio/positions")
    return None if body is None else body["positions"]


async def quote(symbol: str = "SPX") -> Optional[dict]:
    return await _get(f"{get_settings().MARKET_STREAM_URL.rstrip('/')}/v1/quotes/{symbol}")


def latest_rate() -> Optional[float]:
    """Newest 3-month T-bill rate in rates_daily (what the stream bridge prices the quote with)."""
    try:
        conn = get_db_connection()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("no database for the rate: %s", exc)
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT rate FROM rates_daily ORDER BY date DESC LIMIT 1")
            row = cur.fetchone()
            return float(row["rate"]) if row else None
    finally:
        return_db_connection(conn)


EXTREME_DAYS_SQL = """
WITH r AS (
    SELECT u.date, u.close / LAG(u.close) OVER (ORDER BY u.date) - 1 AS spx_return,
           v.close - LAG(v.close) OVER (ORDER BY u.date) AS vix_change
    FROM underlying_daily u LEFT JOIN vix_daily v ON v.date = u.date
    WHERE u.symbol = 'SPX'
)
(SELECT date, spx_return, vix_change FROM r WHERE spx_return IS NOT NULL ORDER BY spx_return LIMIT %s)
UNION ALL
(SELECT date, spx_return, vix_change FROM r WHERE spx_return IS NOT NULL ORDER BY spx_return DESC LIMIT %s)
"""


def extreme_days(falls: int, rises: int) -> Optional[list]:
    """The largest SPX daily falls, then rises, in underlying_daily, with that day's VIX change in points."""
    try:
        conn = get_db_connection()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("no database for history: %s", exc)
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(EXTREME_DAYS_SQL, (falls, rises))
            return [{"date": r["date"], "spx_return": float(r["spx_return"]),
                     "vix_change": None if r["vix_change"] is None else float(r["vix_change"])} for r in cur.fetchall()]
    finally:
        return_db_connection(conn)


DAILY_MOVES_SQL = """
SELECT date, spx_return, vix_change FROM (
    SELECT u.date, u.close / LAG(u.close) OVER (ORDER BY u.date) - 1 AS spx_return,
           v.close - LAG(v.close) OVER (ORDER BY u.date) AS vix_change
    FROM underlying_daily u LEFT JOIN vix_daily v ON v.date = u.date
    WHERE u.symbol = 'SPX'
) r WHERE spx_return IS NOT NULL ORDER BY date
"""


def daily_moves() -> Optional[list]:
    """Every SPX daily return with that day's VIX change in points (0 when VIX is missing), oldest first."""
    try:
        conn = get_db_connection()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("no database for history: %s", exc)
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(DAILY_MOVES_SQL)
            return [(float(r["spx_return"]), float(r["vix_change"] or 0.0)) for r in cur.fetchall()]
    finally:
        return_db_connection(conn)


async def garch_next_sigma() -> Optional[tuple]:
    """(sigma of the next session's log return, the forecast's origin session) from the ml expiry forecasts."""
    body = await _get(f"{get_settings().ML_URL.rstrip('/')}/v1/predict/expiries")
    for row in (body or {}).get("expiries", []):
        path = row.get("variance_path")
        if path:
            return float(path[0]) ** 0.5, body.get("origin_date")
    return None


async def portfolio_closes() -> Optional[list]:
    body = await _get(f"{get_settings().PORTFOLIO_URL.rstrip('/')}/v1/portfolio/equity?kind=close")
    return None if body is None else body["snapshots"]

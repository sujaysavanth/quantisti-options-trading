"""HTTP clients for the portfolio service (net positions) and market-stream (live SPX quote), and the latest
T-bill rate from Postgres. Each returns None when its source is unavailable."""

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

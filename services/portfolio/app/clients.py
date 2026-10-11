"""HTTP clients for the simulator (paper trades, account) and market-stream (live SPX quote).

Each call returns None when the other service is down or answers with an error, so callers can skip and retry.
"""

import logging
from typing import Any, Optional

import httpx

from .config import get_settings

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


class SimulatorClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or get_settings().SIMULATOR_URL).rstrip("/")

    async def orders(self) -> Optional[list]:
        return await _get(f"{self.base_url}/v1/paper/orders")

    async def account(self) -> Optional[dict]:
        return await _get(f"{self.base_url}/v1/paper/account")


class MarketStreamClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or get_settings().MARKET_STREAM_URL).rstrip("/")

    async def spot(self, symbol: str = "SPX") -> Optional[float]:
        quote = await _get(f"{self.base_url}/v1/quotes/{symbol}")
        price = (quote or {}).get("last_price")
        return float(price) if price else None

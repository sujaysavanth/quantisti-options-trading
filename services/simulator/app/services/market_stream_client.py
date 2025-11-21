"""Client for Market Stream Service."""

import logging
from typing import Any, Dict, Optional

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)


class MarketStreamClient:
    """Fetch latest quotes from market-stream service."""

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.MARKET_STREAM_URL.rstrip("/")

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/v1/quotes/{symbol}", timeout=10.0)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning("Quote for %s not found on market stream", symbol)
            else:
                logger.error("Market stream status error: %s", exc)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Error fetching quote from market stream: %s", exc)
        return None

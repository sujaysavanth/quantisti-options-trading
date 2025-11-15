"""Client for fetching data from Market Data Service."""

import logging
from typing import List, Dict, Optional
from datetime import datetime
import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)


class MarketDataClient:
    """Client for interacting with Market Data Service."""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.MARKET_SERVICE_URL

    async def fetch_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[List[Dict]]:
        """Fetch historical OHLC data from market service.

        Args:
            symbol: Underlying symbol (e.g., NIFTY)
            start_date: Start date
            end_date: End date

        Returns:
            List of OHLC data dictionaries
        """
        try:
            # TODO: Replace with actual market service endpoint
            # This is a placeholder - implement based on your market service API
            url = f"{self.base_url}/v1/market/historical/{symbol}"
            params = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=30.0)
                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching market data: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return None

    async def fetch_latest_price(self, symbol: str) -> Optional[float]:
        """Fetch latest price for a symbol.

        Args:
            symbol: Underlying symbol

        Returns:
            Latest closing price
        """
        try:
            # TODO: Implement based on market service API
            url = f"{self.base_url}/v1/market/latest/{symbol}"

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                return data.get('close')

        except Exception as e:
            logger.error(f"Error fetching latest price: {e}")
            return None

"""Client for fetching data from Market Data Service."""

import logging
from typing import List, Dict, Optional
from datetime import datetime, date, timedelta
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
        start_date: date,
        end_date: date
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
            # Market service endpoint for historical data
            url = f"{self.base_url}/v1/nifty/historical"
            params = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }

            logger.info(f"Fetching market data from {url} for {start_date} to {end_date}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                # Extract candle data from response
                # Response format: {"symbol": "NIFTY", "data": [...], "count": N}
                candles = data.get('data', [])

                logger.info(f"Fetched {len(candles)} candles from market service")

                return candles

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching market data: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error fetching market data: {e}")
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
            url = f"{self.base_url}/v1/nifty/spot"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                return data.get('price')

        except Exception as e:
            logger.error(f"Error fetching latest price: {e}")
            return None

    async def fetch_data_for_week(
        self,
        symbol: str,
        week_start: date
    ) -> Optional[List[Dict]]:
        """Fetch data for a specific week (Mon-Fri).

        Args:
            symbol: Underlying symbol
            week_start: Start date of the week (should be Monday)

        Returns:
            List of OHLC data for the week
        """
        # Fetch from week_start to week_end (Friday or 4 days later)
        week_end = week_start + timedelta(days=4)

        return await self.fetch_historical_data(symbol, week_start, week_end)

    async def fetch_data_with_lookback(
        self,
        symbol: str,
        week_start: date,
        lookback_days: int = 60
    ) -> Optional[List[Dict]]:
        """Fetch data for a week plus historical lookback for indicators.

        Args:
            symbol: Underlying symbol
            week_start: Start date of the week
            lookback_days: Number of days to look back (for calculating indicators)

        Returns:
            List of OHLC data including lookback period
        """
        # Get data from lookback period to end of week
        start = week_start - timedelta(days=lookback_days)
        end = week_start + timedelta(days=4)  # End of week (Friday)

        return await self.fetch_historical_data(symbol, start, end)

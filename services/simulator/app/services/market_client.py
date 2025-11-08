"""Client for Market Data API."""

import logging
from datetime import date
from typing import List, Optional, Dict, Any

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)


class MarketDataClient:
    """Client to fetch data from Market Data Service."""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.MARKET_SERVICE_URL

    async def get_spot_price(self, target_date: Optional[date] = None) -> Optional[float]:
        """Get Nifty spot price for a specific date.

        Args:
            target_date: Date to fetch price for (None = latest)

        Returns:
            Spot price or None if not found
        """
        try:
            async with httpx.AsyncClient() as client:
                if target_date:
                    # Fetch historical data for the specific date
                    response = await client.get(
                        f"{self.base_url}/v1/nifty/historical",
                        params={
                            "start_date": str(target_date),
                            "end_date": str(target_date)
                        },
                        timeout=10.0
                    )
                else:
                    # Fetch latest spot price
                    response = await client.get(
                        f"{self.base_url}/v1/nifty/spot",
                        timeout=10.0
                    )

                response.raise_for_status()
                data = response.json()

                if target_date:
                    # Extract from historical data
                    if data.get("data"):
                        return data["data"][0]["close"]
                    return None
                else:
                    # Extract from spot price
                    return data.get("price")

        except Exception as e:
            logger.error(f"Error fetching spot price: {e}")
            return None

    async def get_option_chain(
        self,
        target_date: Optional[date] = None,
        expiry_date: Optional[date] = None,
        strike_range: int = 10
    ) -> Optional[Dict[str, Any]]:
        """Get option chain from Market Data API.

        Args:
            target_date: Date for option chain
            expiry_date: Option expiry date
            strike_range: Number of strikes above/below ATM

        Returns:
            Option chain data or None if not found
        """
        try:
            async with httpx.AsyncClient() as client:
                params = {}
                if target_date:
                    params["date"] = str(target_date)
                if expiry_date:
                    params["expiry_date"] = str(expiry_date)
                if strike_range:
                    params["strike_range"] = strike_range

                response = await client.get(
                    f"{self.base_url}/v1/options/chain",
                    params=params,
                    timeout=30.0
                )

                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"Error fetching option chain: {e}")
            return None

    async def get_option_price(
        self,
        strike: float,
        option_type: str,
        target_date: Optional[date] = None,
        expiry_date: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """Get price for a specific option.

        Args:
            strike: Strike price
            option_type: CE or PE
            target_date: Date for option price
            expiry_date: Option expiry date

        Returns:
            Option data including price and Greeks
        """
        try:
            # Get full option chain and filter for specific strike
            chain = await self.get_option_chain(
                target_date=target_date,
                expiry_date=expiry_date,
                strike_range=20  # Get wider range to ensure we have the strike
            )

            if not chain or not chain.get("options"):
                return None

            # Find the specific option
            for option in chain["options"]:
                if option["strike"] == strike and option["option_type"] == option_type:
                    return {
                        "price": option["price"],
                        "bid": option.get("bid"),
                        "ask": option.get("ask"),
                        "greeks": option.get("greeks"),
                        "implied_volatility": option.get("implied_volatility"),
                        "spot_price": chain["spot_price"],
                        "date": chain["date"],
                        "expiry_date": option["expiry_date"]
                    }

            return None

        except Exception as e:
            logger.error(f"Error fetching option price for strike {strike} {option_type}: {e}")
            return None

    async def get_historical_data(
        self,
        start_date: date,
        end_date: date
    ) -> Optional[List[Dict[str, Any]]]:
        """Get historical Nifty data.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of historical candles
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/nifty/historical",
                    params={
                        "start_date": str(start_date),
                        "end_date": str(end_date)
                    },
                    timeout=30.0
                )

                response.raise_for_status()
                data = response.json()
                return data.get("data", [])

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return None

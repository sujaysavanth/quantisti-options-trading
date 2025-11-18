"""Data provider service for fetching and generating market data."""

import logging
from datetime import date, timedelta
from typing import List, Optional, Dict, Any

import psycopg2
from psycopg2.extras import RealDictCursor

from ..db.connection import get_db_connection, return_db_connection
from ..models.market_data import CandleData
from ..models.options import OptionData, OptionType, Greeks
from ..services.black_scholes import BlackScholesCalculator
from ..services.greeks import GreeksCalculator
from ..config import get_settings

logger = logging.getLogger(__name__)


class DataProvider:
    """Provider for market data and option chain generation."""

    def __init__(self):
        self.settings = get_settings()
        self.bs_calculator = BlackScholesCalculator()
        self.greeks_calculator = GreeksCalculator()

    def get_historical_data(
        self,
        start_date: date,
        end_date: date
    ) -> List[CandleData]:
        """Fetch historical Nifty data from database.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of candle data
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT date, open, high, low, close, volume, historical_volatility
                FROM nifty_historical
                WHERE date >= %s AND date <= %s
                ORDER BY date ASC
            """

            cursor.execute(query, (start_date, end_date))
            rows = cursor.fetchall()

            cursor.close()

            # Convert Decimal to float for each row
            candles = []
            for row in rows:
                candle_dict = {
                    'date': row['date'],
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': int(row['volume']),
                    'historical_volatility': float(row['historical_volatility']) if row['historical_volatility'] else None
                }
                candles.append(CandleData(**candle_dict))

            return candles

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            raise
        finally:
            if conn:
                return_db_connection(conn)

    def get_latest_spot_price(self) -> Optional[Dict[str, Any]]:
        """Get the latest Nifty spot price from database.

        Returns:
            Dictionary with latest spot data or None if no data exists
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT date, close as price, volume, historical_volatility
                FROM nifty_historical
                ORDER BY date DESC
                LIMIT 1
            """

            cursor.execute(query)
            row = cursor.fetchone()
            cursor.close()

            if row:
                # Convert Decimal to float for numeric operations
                return {
                    'date': row['date'],
                    'price': float(row['price']),
                    'volume': int(row['volume']),
                    'historical_volatility': float(row['historical_volatility']) if row['historical_volatility'] else None
                }
            return None

        except Exception as e:
            logger.error(f"Error fetching latest spot price: {e}")
            raise
        finally:
            if conn:
                return_db_connection(conn)

    def get_spot_price_for_date(self, target_date: date) -> Optional[float]:
        """Get Nifty spot price for a specific date.

        Args:
            target_date: Date to fetch price for

        Returns:
            Spot price or None if not found
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT close
                FROM nifty_historical
                WHERE date = %s
            """

            cursor.execute(query, (target_date,))
            row = cursor.fetchone()
            cursor.close()

            return float(row['close']) if row else None

        except Exception as e:
            logger.error(f"Error fetching spot price for date {target_date}: {e}")
            raise
        finally:
            if conn:
                return_db_connection(conn)

    def get_historical_volatility_for_date(self, target_date: date) -> Optional[float]:
        """Get historical volatility for a specific date.

        Args:
            target_date: Date to fetch volatility for

        Returns:
            Historical volatility or default if not found
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT historical_volatility
                FROM nifty_historical
                WHERE date = %s
            """

            cursor.execute(query, (target_date,))
            row = cursor.fetchone()
            cursor.close()

            if row and row['historical_volatility']:
                return float(row['historical_volatility'])
            else:
                # Default volatility if not available
                return 0.15  # 15% default

        except Exception as e:
            logger.error(f"Error fetching volatility for date {target_date}: {e}")
            return 0.15  # Default fallback
        finally:
            if conn:
                return_db_connection(conn)

    def _get_next_expiry(self, current_date: date) -> date:
        """Calculate next weekly expiry (Tuesday for Nifty contracts).

        Args:
            current_date: Current trade date

        Returns:
            Next Tuesday expiry (or the same day if already Tuesday)
        """
        # NSE moved Nifty weekly expiries to Tuesday (weekday=1)
        days_until_tuesday = (1 - current_date.weekday()) % 7
        # If we're already on Tuesday, expiry is today; otherwise move forward
        if days_until_tuesday == 0:
            return current_date
        return current_date + timedelta(days=days_until_tuesday)

    def generate_option_chain(
        self,
        target_date: Optional[date] = None,
        expiry_date: Optional[date] = None,
        strike_range: int = 10
    ) -> Optional[Dict[str, Any]]:
        """Generate option chain with Black-Scholes pricing.

        Args:
            target_date: Date for option chain (None = latest)
            expiry_date: Option expiry date (None = next weekly expiry)
            strike_range: Number of strikes above/below ATM

        Returns:
            Dictionary with option chain data or None if no data
        """
        # Get spot price
        if target_date is None:
            spot_data = self.get_latest_spot_price()
            if not spot_data:
                return None
            spot_price = spot_data['price']
            target_date = spot_data['date']
        else:
            spot_price = self.get_spot_price_for_date(target_date)
            if not spot_price:
                return None

        # Get expiry date
        if expiry_date is None:
            expiry_date = self._get_next_expiry(target_date)

        # Get volatility
        volatility = self.get_historical_volatility_for_date(target_date)

        # Calculate time to expiry
        time_to_expiry = self.bs_calculator.calculate_time_to_expiry(target_date, expiry_date)

        if time_to_expiry <= 0:
            logger.warning(f"Option already expired. Target: {target_date}, Expiry: {expiry_date}")
            return None

        # Generate strike prices (round to nearest 50)
        atm_strike = round(spot_price / 50) * 50
        strike_interval = 50  # Nifty strikes are typically 50 points apart

        strikes = [
            atm_strike + (i * strike_interval)
            for i in range(-strike_range, strike_range + 1)
        ]

        # Generate options for each strike
        options = []
        total_call_oi = 0
        total_put_oi = 0

        for strike in strikes:
            # Call option
            call_price = self.bs_calculator.call_price(
                spot_price, strike, time_to_expiry,
                self.settings.RISK_FREE_RATE, volatility,
                self.settings.DIVIDEND_YIELD
            )

            call_greeks = self.greeks_calculator.calculate_greeks(
                spot_price, strike, time_to_expiry,
                self.settings.RISK_FREE_RATE, volatility,
                "CE", self.settings.DIVIDEND_YIELD
            )

            call_intrinsic = self.bs_calculator.intrinsic_value(spot_price, strike, "CE")
            call_time_value = self.bs_calculator.time_value(call_price, spot_price, strike, "CE")

            # Simulate OI and volume (proportional to moneyness)
            moneyness = abs(spot_price - strike) / spot_price
            oi_factor = max(1.0 - moneyness * 10, 0.1)  # Higher OI near ATM
            call_oi = int(100000 * oi_factor)
            call_volume = int(call_oi * 0.3)  # ~30% of OI traded

            total_call_oi += call_oi

            options.append(OptionData(
                strike=strike,
                option_type=OptionType.CALL,
                expiry_date=expiry_date,
                price=round(call_price, 2),
                bid=round(call_price * 0.995, 2),
                ask=round(call_price * 1.005, 2),
                greeks=call_greeks,
                implied_volatility=round(volatility, 4),
                open_interest=call_oi,
                volume=call_volume,
                intrinsic_value=round(call_intrinsic, 2),
                time_value=round(call_time_value, 2),
                in_the_money=(spot_price > strike)
            ))

            # Put option
            put_price = self.bs_calculator.put_price(
                spot_price, strike, time_to_expiry,
                self.settings.RISK_FREE_RATE, volatility,
                self.settings.DIVIDEND_YIELD
            )

            put_greeks = self.greeks_calculator.calculate_greeks(
                spot_price, strike, time_to_expiry,
                self.settings.RISK_FREE_RATE, volatility,
                "PE", self.settings.DIVIDEND_YIELD
            )

            put_intrinsic = self.bs_calculator.intrinsic_value(spot_price, strike, "PE")
            put_time_value = self.bs_calculator.time_value(put_price, spot_price, strike, "PE")

            put_oi = int(120000 * oi_factor)  # Puts typically have higher OI
            put_volume = int(put_oi * 0.3)

            total_put_oi += put_oi

            options.append(OptionData(
                strike=strike,
                option_type=OptionType.PUT,
                expiry_date=expiry_date,
                price=round(put_price, 2),
                bid=round(put_price * 0.995, 2),
                ask=round(put_price * 1.005, 2),
                greeks=put_greeks,
                implied_volatility=round(volatility, 4),
                open_interest=put_oi,
                volume=put_volume,
                intrinsic_value=round(put_intrinsic, 2),
                time_value=round(put_time_value, 2),
                in_the_money=(spot_price < strike)
            ))

        # Calculate PCR
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0

        return {
            "spot_price": round(spot_price, 2),
            "date": target_date,
            "expiry_date": expiry_date,
            "options": options,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "pcr": round(pcr, 2)
        }

"""Feature computation and storage service."""

import logging
from datetime import datetime, date
from typing import Optional
import pandas as pd
from psycopg2.extras import RealDictCursor
import json

from ..db.connection import get_db_connection, return_db_connection
from ..calculators.price_calculator import PriceFeatureCalculator
from ..calculators.technical_calculator import TechnicalIndicatorCalculator
from ..calculators.volatility_calculator import VolatilityCalculator
from ..services.market_client import MarketDataClient
from ..models.features import WeeklyFeatures, PriceFeatures, TechnicalIndicators, VolatilityFeatures

logger = logging.getLogger(__name__)


class FeatureService:
    """Service for computing and managing features."""

    def __init__(self):
        self.price_calc = PriceFeatureCalculator()
        self.technical_calc = TechnicalIndicatorCalculator()
        self.volatility_calc = VolatilityCalculator()
        self.market_client = MarketDataClient()

    async def compute_weekly_features(
        self,
        symbol: str,
        week_start_date: datetime
    ) -> Optional[WeeklyFeatures]:
        """Compute all features for a given week.

        Args:
            symbol: Underlying symbol
            week_start_date: Start date of the week

        Returns:
            WeeklyFeatures object with all computed features
        """
        try:
            logger.info(f"Computing features for {symbol} week starting {week_start_date}")

            # Convert datetime to date
            week_start = week_start_date.date() if isinstance(week_start_date, datetime) else week_start_date

            # Fetch market data with lookback for indicator calculation
            market_data = await self.market_client.fetch_data_with_lookback(
                symbol=symbol,
                week_start=week_start,
                lookback_days=60  # 60 days should cover 50-day MA and other indicators
            )

            if not market_data:
                logger.error(f"No market data returned for {symbol} week {week_start}")
                return None

            if len(market_data) == 0:
                logger.error(f"Empty market data for {symbol} week {week_start}")
                return None

            # Convert to pandas DataFrame
            df = pd.DataFrame(market_data)

            # Ensure numeric columns
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

            # Sort by date
            df = df.sort_values('date')

            logger.info(f"Computing features from {len(df)} candles")

            # Compute all features
            price_features = PriceFeatures(**self.price_calc.calculate_all(df))
            technical_features = TechnicalIndicators(**self.technical_calc.calculate_all(df))
            volatility_features = VolatilityFeatures(**self.volatility_calc.calculate_all(df))

            features = WeeklyFeatures(
                week_start_date=week_start_date,
                symbol=symbol,
                price_features=price_features,
                technical_indicators=technical_features,
                volatility_features=volatility_features,
                created_at=datetime.utcnow()
            )

            logger.info(f"Successfully computed features for {symbol} week {week_start}")
            return features

        except Exception as e:
            logger.error(f"Error computing features: {e}", exc_info=True)
            return None

    def save_features(self, features: WeeklyFeatures) -> bool:
        """Save computed features to database.

        Args:
            features: WeeklyFeatures object

        Returns:
            True if successful, False otherwise
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Extract feature values
            week_start = features.week_start_date.date() if isinstance(features.week_start_date, datetime) else features.week_start_date

            # Price features
            price = features.price_features
            weekly_change_pct = price.weekly_change_pct if price else None
            weekly_high_low_range_pct = price.weekly_high_low_range_pct if price else None
            volume_ratio = price.volume_ratio if price else None

            # Technical indicators
            tech = features.technical_indicators
            rsi_14 = tech.rsi_14 if tech else None
            macd = tech.macd if tech else None
            macd_signal = tech.macd_signal if tech else None
            bb_width = tech.bb_width if tech else None

            # Volatility features
            vol = features.volatility_features
            historical_vol_10d = vol.historical_vol_10d if vol else None
            historical_vol_20d = vol.historical_vol_20d if vol else None
            atr_14 = vol.atr_14 if vol else None

            # Insert or update features
            cursor.execute(
                """
                INSERT INTO weekly_features
                (week_start_date, symbol, weekly_change_pct, weekly_high_low_range_pct, volume_ratio,
                 rsi_14, macd, macd_signal, bb_width, historical_vol_10d, historical_vol_20d, atr_14,
                 created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (week_start_date, symbol)
                DO UPDATE SET
                    weekly_change_pct = EXCLUDED.weekly_change_pct,
                    weekly_high_low_range_pct = EXCLUDED.weekly_high_low_range_pct,
                    volume_ratio = EXCLUDED.volume_ratio,
                    rsi_14 = EXCLUDED.rsi_14,
                    macd = EXCLUDED.macd,
                    macd_signal = EXCLUDED.macd_signal,
                    bb_width = EXCLUDED.bb_width,
                    historical_vol_10d = EXCLUDED.historical_vol_10d,
                    historical_vol_20d = EXCLUDED.historical_vol_20d,
                    atr_14 = EXCLUDED.atr_14,
                    updated_at = NOW()
                """,
                (week_start, features.symbol, weekly_change_pct, weekly_high_low_range_pct,
                 volume_ratio, rsi_14, macd, macd_signal, bb_width,
                 historical_vol_10d, historical_vol_20d, atr_14)
            )

            conn.commit()
            cursor.close()

            logger.info(f"Saved features for {features.symbol} week {week_start}")
            return True

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error saving features: {e}", exc_info=True)
            return False

        finally:
            if conn:
                return_db_connection(conn)

    def get_features(
        self,
        symbol: str,
        week_start_date: datetime
    ) -> Optional[WeeklyFeatures]:
        """Retrieve features from database.

        Args:
            symbol: Underlying symbol
            week_start_date: Start date of the week

        Returns:
            WeeklyFeatures object or None if not found
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Convert datetime to date
            week_start = week_start_date.date() if isinstance(week_start_date, datetime) else week_start_date

            cursor.execute(
                "SELECT * FROM weekly_features WHERE symbol = %s AND week_start_date = %s",
                (symbol, week_start)
            )
            result = cursor.fetchone()

            cursor.close()

            if not result:
                logger.info(f"No features found for {symbol} week {week_start}")
                return None

            # Reconstruct feature objects
            price_features = PriceFeatures(
                weekly_change_pct=result['weekly_change_pct'],
                weekly_high_low_range_pct=result['weekly_high_low_range_pct'],
                volume_ratio=result['volume_ratio']
            )

            technical_features = TechnicalIndicators(
                rsi_14=result['rsi_14'],
                macd=result['macd'],
                macd_signal=result['macd_signal'],
                bb_width=result['bb_width']
            )

            volatility_features = VolatilityFeatures(
                historical_vol_10d=result['historical_vol_10d'],
                historical_vol_20d=result['historical_vol_20d'],
                atr_14=result['atr_14']
            )

            features = WeeklyFeatures(
                week_start_date=result['week_start_date'],
                symbol=result['symbol'],
                price_features=price_features,
                technical_indicators=technical_features,
                volatility_features=volatility_features,
                created_at=result['created_at']
            )

            logger.info(f"Retrieved features for {symbol} week {week_start}")
            return features

        except Exception as e:
            logger.error(f"Error retrieving features: {e}", exc_info=True)
            return None

        finally:
            if conn:
                return_db_connection(conn)

    def get_latest_features(self, symbol: str) -> Optional[WeeklyFeatures]:
        """Get most recent features for a symbol.

        Args:
            symbol: Underlying symbol

        Returns:
            Latest WeeklyFeatures or None
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute(
                """
                SELECT * FROM weekly_features
                WHERE symbol = %s
                ORDER BY week_start_date DESC
                LIMIT 1
                """,
                (symbol,)
            )
            result = cursor.fetchone()

            cursor.close()

            if not result:
                return None

            # Reconstruct feature objects (same as get_features)
            price_features = PriceFeatures(
                weekly_change_pct=result['weekly_change_pct'],
                weekly_high_low_range_pct=result['weekly_high_low_range_pct'],
                volume_ratio=result['volume_ratio']
            )

            technical_features = TechnicalIndicators(
                rsi_14=result['rsi_14'],
                macd=result['macd'],
                macd_signal=result['macd_signal'],
                bb_width=result['bb_width']
            )

            volatility_features = VolatilityFeatures(
                historical_vol_10d=result['historical_vol_10d'],
                historical_vol_20d=result['historical_vol_20d'],
                atr_14=result['atr_14']
            )

            features = WeeklyFeatures(
                week_start_date=result['week_start_date'],
                symbol=result['symbol'],
                price_features=price_features,
                technical_indicators=technical_features,
                volatility_features=volatility_features,
                created_at=result['created_at']
            )

            return features

        except Exception as e:
            logger.error(f"Error retrieving latest features: {e}", exc_info=True)
            return None

        finally:
            if conn:
                return_db_connection(conn)

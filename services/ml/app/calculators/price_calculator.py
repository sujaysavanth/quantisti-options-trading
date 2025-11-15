"""Price-based feature calculator."""

import logging
import pandas as pd
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PriceFeatureCalculator:
    """Calculate price-based features from market data."""

    @staticmethod
    def calculate_weekly_change(data: pd.DataFrame) -> Optional[float]:
        """Calculate weekly percentage change.

        Args:
            data: DataFrame with OHLC data (must have 'close' column)

        Returns:
            Weekly percentage change
        """
        try:
            if len(data) < 5:  # Need at least a week of data
                return None

            # Get first and last close of the week
            first_close = data.iloc[0]['close']
            last_close = data.iloc[-1]['close']

            if first_close == 0:
                return None

            change_pct = ((last_close - first_close) / first_close) * 100
            return round(change_pct, 2)

        except Exception as e:
            logger.error(f"Error calculating weekly change: {e}")
            return None

    @staticmethod
    def calculate_weekly_range(data: pd.DataFrame) -> Optional[float]:
        """Calculate weekly high-low range percentage.

        Args:
            data: DataFrame with OHLC data (must have 'high', 'low' columns)

        Returns:
            Weekly range as percentage of closing price
        """
        try:
            if data.empty:
                return None

            weekly_high = data['high'].max()
            weekly_low = data['low'].min()
            close = data.iloc[-1]['close']

            if close == 0:
                return None

            range_pct = ((weekly_high - weekly_low) / close) * 100
            return round(range_pct, 2)

        except Exception as e:
            logger.error(f"Error calculating weekly range: {e}")
            return None

    @staticmethod
    def calculate_volume_ratio(data: pd.DataFrame, lookback: int = 20) -> Optional[float]:
        """Calculate volume ratio vs average.

        Args:
            data: DataFrame with volume data (must have 'volume' column)
            lookback: Number of periods for average calculation

        Returns:
            Current volume / average volume
        """
        try:
            if len(data) < lookback:
                return None

            current_volume = data.iloc[-1]['volume']
            avg_volume = data['volume'].tail(lookback).mean()

            if avg_volume == 0:
                return None

            ratio = current_volume / avg_volume
            return round(ratio, 2)

        except Exception as e:
            logger.error(f"Error calculating volume ratio: {e}")
            return None

    def calculate_all(self, data: pd.DataFrame) -> Dict[str, Optional[float]]:
        """Calculate all price features.

        Args:
            data: DataFrame with OHLC data

        Returns:
            Dictionary with all price features
        """
        return {
            'weekly_change_pct': self.calculate_weekly_change(data),
            'weekly_high_low_range_pct': self.calculate_weekly_range(data),
            'volume_ratio': self.calculate_volume_ratio(data)
        }

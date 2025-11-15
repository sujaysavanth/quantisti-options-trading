"""Volatility feature calculator."""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class VolatilityCalculator:
    """Calculate volatility-based features from market data."""

    @staticmethod
    def calculate_historical_volatility(data: pd.DataFrame, period: int = 10) -> Optional[float]:
        """Calculate historical volatility (annualized).

        Args:
            data: DataFrame with price data (must have 'close' column)
            period: Lookback period for volatility calculation

        Returns:
            Annualized historical volatility percentage
        """
        try:
            if len(data) < period + 1:
                return None

            closes = data['close'].values

            # Calculate log returns
            log_returns = np.log(closes[1:] / closes[:-1])

            # Calculate standard deviation of returns
            std_returns = np.std(log_returns[-period:])

            # Annualize (assuming 252 trading days)
            annual_vol = std_returns * np.sqrt(252) * 100

            return round(annual_vol, 2)

        except Exception as e:
            logger.error(f"Error calculating historical volatility: {e}")
            return None

    @staticmethod
    def calculate_atr(data: pd.DataFrame, period: int = 14) -> Optional[float]:
        """Calculate ATR (Average True Range).

        Args:
            data: DataFrame with OHLC data (must have 'high', 'low', 'close' columns)
            period: ATR period

        Returns:
            ATR value
        """
        try:
            if len(data) < period + 1:
                return None

            high = data['high'].values
            low = data['low'].values
            close = data['close'].values

            # Calculate True Range
            tr1 = high[1:] - low[1:]
            tr2 = np.abs(high[1:] - close[:-1])
            tr3 = np.abs(low[1:] - close[:-1])

            tr = np.maximum(tr1, np.maximum(tr2, tr3))

            # Calculate ATR as simple moving average of TR
            atr = np.mean(tr[-period:])

            return round(atr, 2)

        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return None

    def calculate_all(self, data: pd.DataFrame) -> Dict[str, Optional[float]]:
        """Calculate all volatility features.

        Args:
            data: DataFrame with OHLC data

        Returns:
            Dictionary with all volatility features
        """
        return {
            'historical_vol_10d': self.calculate_historical_volatility(data, 10),
            'historical_vol_20d': self.calculate_historical_volatility(data, 20),
            'atr_14': self.calculate_atr(data, 14)
        }

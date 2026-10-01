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

    @staticmethod
    def calculate_vix_features(vix: Optional[pd.DataFrame], as_of, hv_20d: Optional[float]) -> Dict[str, Optional[float]]:
        """Implied-volatility features from VIX closes up to `as_of`.

        Args:
            vix: DataFrame with 'date' and 'close' columns (VIX in vol points)
            as_of: Last date the features may use
            hv_20d: 20-day realised volatility in percent, for the variance risk premium

        Returns:
            vix_close, vix_change_1w (points over the previous 5 sessions) and
            vix_hv_spread (VIX minus 20-day realised vol: the premium option
            sellers collect when positive)
        """
        empty = {'vix_close': None, 'vix_change_1w': None, 'vix_hv_spread': None}
        if vix is None or vix.empty:
            return empty
        series = vix[vix['date'] <= as_of].sort_values('date')['close'].astype(float)
        if series.empty:
            return empty
        close = float(series.iloc[-1])
        change = close - float(series.iloc[-6]) if len(series) >= 6 else None
        return {
            'vix_close': round(close, 2),
            'vix_change_1w': round(change, 2) if change is not None else None,
            'vix_hv_spread': round(close - hv_20d, 2) if hv_20d is not None else None,
        }

    def calculate_all(self, data: pd.DataFrame, vix: Optional[pd.DataFrame] = None) -> Dict[str, Optional[float]]:
        """Calculate all volatility features.

        Args:
            data: DataFrame with OHLC data
            vix: Optional VIX closes ('date', 'close') covering the same window

        Returns:
            Dictionary with all volatility features
        """
        hv_20 = self.calculate_historical_volatility(data, 20)
        features = {
            'historical_vol_10d': self.calculate_historical_volatility(data, 10),
            'historical_vol_20d': hv_20,
            'atr_14': self.calculate_atr(data, 14),
        }
        if 'date' in data.columns:
            features.update(self.calculate_vix_features(vix, data['date'].max(), hv_20))
        return features

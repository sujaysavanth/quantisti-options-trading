"""Technical indicator calculator."""

import logging
import pandas as pd
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TechnicalIndicatorCalculator:
    """Calculate technical indicators from market data."""

    @staticmethod
    def calculate_rsi(data: pd.DataFrame, period: int = 14) -> Optional[float]:
        """Calculate RSI (Relative Strength Index).

        Args:
            data: DataFrame with price data (must have 'close' column)
            period: RSI period (default 14)

        Returns:
            RSI value (0-100)
        """
        try:
            if len(data) < period + 1:
                return None

            closes = data['close'].values
            deltas = pd.Series(closes).diff()

            gain = deltas.where(deltas > 0, 0).rolling(window=period).mean()
            loss = -deltas.where(deltas < 0, 0).rolling(window=period).mean()

            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            return round(rsi.iloc[-1], 2) if not pd.isna(rsi.iloc[-1]) else None

        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return None

    @staticmethod
    def calculate_macd(data: pd.DataFrame,
                      fast: int = 12,
                      slow: int = 26,
                      signal: int = 9) -> Dict[str, Optional[float]]:
        """Calculate MACD (Moving Average Convergence Divergence).

        Args:
            data: DataFrame with price data (must have 'close' column)
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period

        Returns:
            Dictionary with macd and signal values
        """
        try:
            if len(data) < slow + signal:
                return {'macd': None, 'macd_signal': None}

            closes = data['close']

            ema_fast = closes.ewm(span=fast, adjust=False).mean()
            ema_slow = closes.ewm(span=slow, adjust=False).mean()

            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()

            return {
                'macd': round(macd_line.iloc[-1], 2) if not pd.isna(macd_line.iloc[-1]) else None,
                'macd_signal': round(signal_line.iloc[-1], 2) if not pd.isna(signal_line.iloc[-1]) else None
            }

        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return {'macd': None, 'macd_signal': None}

    @staticmethod
    def calculate_bollinger_bands(data: pd.DataFrame,
                                  period: int = 20,
                                  std_dev: int = 2) -> Optional[float]:
        """Calculate Bollinger Bands width.

        Args:
            data: DataFrame with price data (must have 'close' column)
            period: Moving average period
            std_dev: Number of standard deviations

        Returns:
            Bollinger Bands width as percentage
        """
        try:
            if len(data) < period:
                return None

            closes = data['close']

            sma = closes.rolling(window=period).mean()
            std = closes.rolling(window=period).std()

            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)

            width = ((upper_band - lower_band) / sma) * 100

            return round(width.iloc[-1], 2) if not pd.isna(width.iloc[-1]) else None

        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return None

    def calculate_all(self, data: pd.DataFrame) -> Dict[str, Optional[float]]:
        """Calculate all technical indicators.

        Args:
            data: DataFrame with OHLC data

        Returns:
            Dictionary with all technical indicators
        """
        macd_values = self.calculate_macd(data)

        return {
            'rsi_14': self.calculate_rsi(data, 14),
            'macd': macd_values['macd'],
            'macd_signal': macd_values['macd_signal'],
            'bb_width': self.calculate_bollinger_bands(data, 20, 2)
        }

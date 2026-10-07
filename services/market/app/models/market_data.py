"""Pydantic models for market data endpoints."""

from datetime import date, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class CandleData(BaseModel):
    """OHLCV candle data."""

    date: date
    open: float = Field(..., gt=0, description="Opening price")
    high: float = Field(..., gt=0, description="Highest price")
    low: float = Field(..., gt=0, description="Lowest price")
    close: float = Field(..., gt=0, description="Closing price")
    volume: int = Field(..., ge=0, description="Trading volume")
    historical_volatility: Optional[float] = Field(None, ge=0, le=5, description="Annualized historical volatility")

    @field_validator('high')
    @classmethod
    def validate_high(cls, v, info):
        """Ensure high >= low."""
        if 'low' in info.data and v < info.data['low']:
            raise ValueError('high must be >= low')
        return v

    @field_validator('low')
    @classmethod
    def validate_low(cls, v, info):
        """Ensure low <= open and low <= close."""
        if 'open' in info.data and v > info.data['open']:
            raise ValueError('low must be <= open')
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "date": "2026-09-30",
                "open": 7660.12,
                "high": 7688.40,
                "low": 7640.03,
                "close": 7651.54,
                "volume": 2850000000,
                "historical_volatility": 0.0984
            }
        }
    }


class UnderlyingSpotResponse(BaseModel):
    """Latest close of the underlying index."""

    symbol: str = "SPX"
    price: float = Field(..., gt=0, description="Current spot price")
    timestamp: datetime
    change: Optional[float] = Field(None, description="Price change from previous close")
    change_percent: Optional[float] = Field(None, description="Percentage change")
    volume: Optional[int] = Field(None, ge=0, description="Current volume")

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "SPX",
                "price": 7651.54,
                "timestamp": "2026-09-30T16:00:00-04:00",
                "change": -19.30,
                "change_percent": -0.25,
                "volume": 2850000000
            }
        }
    }


class UnderlyingHistoryResponse(BaseModel):
    """Historical daily candles for the underlying index."""

    symbol: str = "SPX"
    data: List[CandleData]
    count: int = Field(..., ge=0, description="Number of candles returned")
    start_date: date
    end_date: date

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "SPX",
                "count": 2,
                "start_date": "2026-09-29",
                "end_date": "2026-09-30",
                "data": [
                    {
                        "date": "2026-09-30",
                        "open": 7660.12,
                        "high": 7688.40,
                        "low": 7640.03,
                        "close": 7651.54,
                        "volume": 2850000000,
                        "historical_volatility": 0.0984
                    }
                ]
            }
        }
    }


class IntradayBar(BaseModel):
    """One intraday OHLCV bar; `ts` is the bar start (UTC)."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = Field(..., ge=0)
    source: str = Field(..., description="'yahoo' (vendor bar) or 'agg_1m' (5m built from 1m bars)")


class IntradayResponse(BaseModel):
    """Intraday bars for one session (ET calendar day)."""

    symbol: Literal["SPX", "VIX"]
    interval: Literal["1m", "5m", "1h"]
    date: date
    count: int = Field(..., ge=0)
    expected: int = Field(..., ge=0, description="Bars in a complete session (390 1m bars on a normal day, 210 on an early close)")
    data: List[IntradayBar]


class HistoricalDataQuery(BaseModel):
    """Query parameters for historical data."""

    start_date: date = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: date = Field(..., description="End date (YYYY-MM-DD)")

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v, info):
        """Ensure end_date >= start_date."""
        if 'start_date' in info.data and v < info.data['start_date']:
            raise ValueError('end_date must be >= start_date')
        return v

    @field_validator('start_date')
    @classmethod
    def validate_start_date_not_future(cls, v):
        """Ensure start_date is not in the future."""
        if v > date.today():
            raise ValueError('start_date cannot be in the future')
        return v

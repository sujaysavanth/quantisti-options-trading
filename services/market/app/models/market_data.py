"""Pydantic models for market data endpoints."""

from datetime import date, datetime
from typing import List, Optional
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
                "date": "2024-01-15",
                "open": 21650.50,
                "high": 21725.80,
                "low": 21580.25,
                "close": 21698.85,
                "volume": 285000000,
                "historical_volatility": 0.1245
            }
        }
    }


class NiftySpotResponse(BaseModel):
    """Current Nifty spot price and metadata."""

    symbol: str = "NIFTY"
    price: float = Field(..., gt=0, description="Current spot price")
    timestamp: datetime
    change: Optional[float] = Field(None, description="Price change from previous close")
    change_percent: Optional[float] = Field(None, description="Percentage change")
    volume: Optional[int] = Field(None, ge=0, description="Current volume")

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "NIFTY",
                "price": 21698.85,
                "timestamp": "2024-01-15T15:30:00",
                "change": 125.50,
                "change_percent": 0.58,
                "volume": 285000000
            }
        }
    }


class NiftyHistoricalResponse(BaseModel):
    """Historical Nifty data response."""

    symbol: str = "NIFTY"
    data: List[CandleData]
    count: int = Field(..., ge=0, description="Number of candles returned")
    start_date: date
    end_date: date

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "NIFTY",
                "count": 2,
                "start_date": "2024-01-15",
                "end_date": "2024-01-16",
                "data": [
                    {
                        "date": "2024-01-15",
                        "open": 21650.50,
                        "high": 21725.80,
                        "low": 21580.25,
                        "close": 21698.85,
                        "volume": 285000000,
                        "historical_volatility": 0.1245
                    }
                ]
            }
        }
    }


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

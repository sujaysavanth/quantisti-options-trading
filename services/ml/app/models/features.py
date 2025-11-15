"""Feature models and schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PriceFeatures(BaseModel):
    """Price-based features."""
    weekly_change_pct: Optional[float] = Field(None, description="Weekly % price change")
    weekly_high_low_range_pct: Optional[float] = Field(None, description="Weekly H-L range %")
    volume_ratio: Optional[float] = Field(None, description="Volume vs 20-week average")


class TechnicalIndicators(BaseModel):
    """Technical indicator features."""
    rsi_14: Optional[float] = Field(None, description="14-period RSI")
    macd: Optional[float] = Field(None, description="MACD value")
    macd_signal: Optional[float] = Field(None, description="MACD signal line")
    bb_width: Optional[float] = Field(None, description="Bollinger Bands width")


class VolatilityFeatures(BaseModel):
    """Volatility-based features."""
    historical_vol_10d: Optional[float] = Field(None, description="10-day historical volatility")
    historical_vol_20d: Optional[float] = Field(None, description="20-day historical volatility")
    atr_14: Optional[float] = Field(None, description="14-period ATR")


class WeeklyFeatures(BaseModel):
    """Complete weekly feature set."""
    week_start_date: datetime
    symbol: str

    # Feature categories
    price_features: Optional[PriceFeatures] = None
    technical_indicators: Optional[TechnicalIndicators] = None
    volatility_features: Optional[VolatilityFeatures] = None

    # Metadata
    created_at: Optional[datetime] = None


class FeatureComputeRequest(BaseModel):
    """Request to compute features."""
    symbol: str = Field(..., description="Underlying symbol (e.g., NIFTY)")
    week_start_date: datetime = Field(..., description="Start date of the week")
    force_recompute: bool = Field(False, description="Force recompute even if exists")


class FeatureResponse(BaseModel):
    """Response with computed features."""
    features: WeeklyFeatures
    message: str = "Features computed successfully"


class FeatureListResponse(BaseModel):
    """Response with list of features."""
    features: list[WeeklyFeatures]
    count: int

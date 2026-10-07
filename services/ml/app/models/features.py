"""Feature models and schemas."""

from datetime import date, datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class PriceFeatures(BaseModel):
    """Price-based features for the week."""
    weekly_change_pct: Optional[float] = Field(None, description="% change from the previous week's close to this week's")
    weekly_high_low_range_pct: Optional[float] = Field(None, description="Week's high-low range as % of its close")
    volume_ratio: Optional[float] = Field(None, description="Last session's volume vs its 20-session average")


class TechnicalIndicators(BaseModel):
    """Technical indicator features at the week's close."""
    rsi_14: Optional[float] = Field(None, description="14-period RSI (simple averages)")
    macd: Optional[float] = Field(None, description="MACD 12/26 (index points)")
    macd_signal: Optional[float] = Field(None, description="MACD signal line, 9-period EMA")
    bb_width: Optional[float] = Field(None, description="Bollinger Bands (20, 2) width as % of the middle band")


class VolatilityFeatures(BaseModel):
    """Volatility-based features at the week's close."""
    historical_vol_10d: Optional[float] = Field(None, description="10-day historical volatility, annualised %")
    historical_vol_20d: Optional[float] = Field(None, description="20-day historical volatility, annualised %")
    atr_14: Optional[float] = Field(None, description="14-period ATR (index points)")
    vix_close: Optional[float] = Field(None, description="VIX close at the week's last session (vol points)")
    vix_change_1w: Optional[float] = Field(None, description="VIX change since the previous week's close (points)")
    vix_hv_spread: Optional[float] = Field(None, description="VIX minus 20-day realised vol (variance risk premium proxy)")


class WeeklyFeatures(BaseModel):
    """Complete weekly feature set, as of the week's last close (its anchor)."""
    week_start_date: date = Field(..., description="Monday of the week")
    anchor_date: Optional[date] = Field(None, description="The week's last session; features use data up to its close")
    symbol: str

    price_features: Optional[PriceFeatures] = None
    technical_indicators: Optional[TechnicalIndicators] = None
    volatility_features: Optional[VolatilityFeatures] = None
    model_features: Optional[Dict[str, Optional[float]]] = Field(
        None, description="The scale-free features the range forecast uses (app/dataset/features.py MODEL_FEATURES)")
    feature_version: Optional[int] = None

    created_at: Optional[datetime] = None


class FeatureComputeRequest(BaseModel):
    """Request to compute features."""
    symbol: str = Field("SPX", description="Underlying symbol (only SPX is loaded)")
    week_start_date: date = Field(..., description="Any day of the week")
    force_recompute: bool = Field(False, description="Rebuild every week even if this one is stored")


class FeatureResponse(BaseModel):
    """Response with computed features."""
    features: WeeklyFeatures
    message: str = "Features computed successfully"

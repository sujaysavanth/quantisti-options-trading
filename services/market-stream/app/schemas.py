"""Pydantic schemas for quote ingestion and streaming."""

from datetime import datetime, date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class OptionLegQuote(BaseModel):
    identifier: str = Field(..., description="Unique option identifier (OCC symbol), e.g., SPXW261002P07600000")
    strike: float
    option_type: Literal["CALL", "PUT"]
    expiry: date
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    iv: Optional[float] = Field(default=None, description="Implied volatility for the leg")


class QuoteUpsert(BaseModel):
    symbol: str = Field(..., description="Underlying symbol, e.g., SPX")
    last_price: float = Field(..., ge=0)
    change: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    spot_iv: Optional[float] = Field(default=None, description="Implied volatility at ATM")
    legs: List[OptionLegQuote] = Field(default_factory=list)
    # Where the quotes come from and how stale they are, so the UI can label them honestly.
    source: Optional[str] = Field(default=None, description="Data source, e.g. cboe")
    delay_minutes: Optional[int] = Field(default=None, ge=0, description="Delay of the source's quotes")
    quoted_at: Optional[datetime] = Field(default=None, description="Time the option quotes are from")


class QuoteSnapshot(QuoteUpsert):
    received_at: datetime = Field(default_factory=datetime.utcnow)

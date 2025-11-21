"""Pydantic schemas for quote ingestion and streaming."""

from datetime import datetime, date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class OptionLegQuote(BaseModel):
    identifier: str = Field(..., description="Unique option identifier, e.g., NIFTY25NOV19500PE")
    strike: float
    option_type: Literal["CALL", "PUT"]
    expiry: date
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    iv: Optional[float] = Field(default=None, description="Implied volatility for the leg")


class QuoteUpsert(BaseModel):
    symbol: str = Field(..., description="Underlying symbol, e.g., NIFTY")
    last_price: float = Field(..., ge=0)
    change: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    spot_iv: Optional[float] = Field(default=None, description="Implied volatility at ATM")
    legs: List[OptionLegQuote] = Field(default_factory=list)


class QuoteSnapshot(QuoteUpsert):
    received_at: datetime = Field(default_factory=datetime.utcnow)

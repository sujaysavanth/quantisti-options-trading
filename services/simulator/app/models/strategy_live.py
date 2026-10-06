"""Pydantic models for live strategy suggestions."""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel


class StrategyLeg(BaseModel):
    identifier: Optional[str]
    strike: float
    option_type: Literal["CALL", "PUT"]
    expiry: str
    quantity: int
    side: Literal["BUY", "SELL"]
    price: Optional[float] = None


class StrategyInstance(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    net_premium: float
    max_profit: Optional[float]
    max_loss: Optional[float]
    breakevens: List[float] = []
    legs: List[StrategyLeg]
    # Copied from the market-stream quote the strategy was built from.
    spot_price: Optional[float] = None
    source: Optional[str] = None
    delay_minutes: Optional[int] = None
    quoted_at: Optional[datetime] = None

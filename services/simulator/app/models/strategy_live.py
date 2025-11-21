"""Pydantic models for live strategy suggestions."""

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

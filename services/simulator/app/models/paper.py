"""Pydantic models for paper trading endpoints."""

from datetime import date, datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PaperLegInput(BaseModel):
    identifier: Optional[str] = Field(
        default=None,
        description="Option identifier from market-stream. If omitted, strike+type+expiry are used."
    )
    strike: float
    option_type: Literal["CALL", "PUT"]
    expiry: date
    quantity: int = Field(default=1, gt=0)
    side: Literal["BUY", "SELL"] = "BUY"


class PaperTradeCreate(BaseModel):
    symbol: str = "NIFTY"
    nickname: Optional[str] = None
    legs: List[PaperLegInput]


class PaperLegState(BaseModel):
    identifier: Optional[str]
    strike: float
    option_type: Literal["CALL", "PUT"]
    expiry: date
    quantity: int
    side: Literal["BUY", "SELL"]
    entry_price: Optional[float]
    current_price: Optional[float]
    pnl: float


class PaperTradeResponse(BaseModel):
    id: UUID
    symbol: str
    nickname: Optional[str]
    created_at: datetime
    entry_notional: float
    current_notional: float
    pnl: float
    legs: List[PaperLegState]

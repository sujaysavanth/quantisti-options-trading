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
    symbol: str = "SPX"
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
    exit_price: Optional[float] = None
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
    status: Literal["open", "closed"] = "open"
    expiry: Optional[date] = None
    settles_at: Optional[datetime] = Field(default=None, description="when an open trade is auto-settled (30 min before the close)")
    closed_at: Optional[datetime] = None
    close_reason: Optional[str] = None
    capital_held: Optional[float] = Field(default=None, description="max loss (defined risk) or margin, open trades only")
    capital_basis: Optional[str] = None


class PaperAccount(BaseModel):
    starting_balance: float
    realised_pnl: float
    unrealised_pnl: float
    total_pnl: float
    account_value: float
    capital_held: float
    available: float
    open_trades: int
    closed_trades: int

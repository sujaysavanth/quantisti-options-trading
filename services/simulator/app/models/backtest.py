"""Pydantic models for backtesting."""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BacktestStatus(str, Enum):
    """Backtest execution status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EntryLogic(str, Enum):
    """Entry logic for backtests."""
    ON_DATE = "ON_DATE"  # Enter on specific date
    DAILY = "DAILY"  # Enter daily
    WEEKLY = "WEEKLY"  # Enter weekly (Mondays)
    MONTHLY = "MONTHLY"  # Enter monthly (first trading day)


class ExitLogic(str, Enum):
    """Exit logic for backtests."""
    ON_EXPIRY = "ON_EXPIRY"  # Hold till expiry
    STOP_LOSS = "STOP_LOSS"  # Exit on stop loss
    TARGET = "TARGET"  # Exit on target
    DAYS = "DAYS"  # Exit after N days


class TradeStatus(str, Enum):
    """Trade status."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class BacktestCreate(BaseModel):
    """Create a new backtest."""
    strategy_id: UUID = Field(..., description="Strategy to backtest")
    name: str = Field(..., min_length=1, max_length=100, description="Backtest name")
    start_date: date = Field(..., description="Start date for backtest")
    end_date: date = Field(..., description="End date for backtest")
    initial_capital: float = Field(default=100000.0, gt=0, description="Initial capital in INR")
    entry_logic: EntryLogic = Field(default=EntryLogic.ON_DATE, description="When to enter trades")
    exit_logic: ExitLogic = Field(default=ExitLogic.ON_EXPIRY, description="When to exit trades")
    stop_loss_pct: Optional[float] = Field(None, gt=0, le=100, description="Stop loss percentage")
    target_pct: Optional[float] = Field(None, gt=0, description="Target profit percentage")
    max_holding_days: Optional[int] = Field(None, gt=0, le=365, description="Maximum holding days")

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v, info):
        """Ensure end_date >= start_date."""
        if 'start_date' in info.data and v < info.data['start_date']:
            raise ValueError('end_date must be >= start_date')
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "strategy_id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Long Straddle - Jan 2024",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "initial_capital": 100000,
                "entry_logic": "ON_DATE",
                "exit_logic": "ON_EXPIRY",
                "stop_loss_pct": 50,
                "target_pct": 100,
                "max_holding_days": 30
            }
        }
    }


class TradeLeg(BaseModel):
    """Individual leg of a trade."""
    id: UUID
    action: str
    option_type: str
    strike: float
    expiry_date: date
    quantity: int
    entry_price: float
    exit_price: Optional[float] = None
    entry_iv: Optional[float] = None
    exit_iv: Optional[float] = None
    pnl: Optional[float] = None


class Trade(BaseModel):
    """Individual trade in a backtest."""
    id: UUID
    trade_number: int
    entry_date: date
    exit_date: Optional[date] = None
    expiry_date: date
    entry_spot_price: float
    exit_spot_price: Optional[float] = None
    entry_premium: float
    exit_premium: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    status: TradeStatus
    exit_reason: Optional[str] = None
    holding_days: Optional[int] = None
    legs: List[TradeLeg] = []


class BacktestResponse(BaseModel):
    """Backtest response model."""
    id: UUID
    strategy_id: UUID
    name: str
    start_date: date
    end_date: date
    initial_capital: float
    entry_logic: EntryLogic
    exit_logic: ExitLogic
    stop_loss_pct: Optional[float] = None
    target_pct: Optional[float] = None
    max_holding_days: Optional[int] = None
    status: BacktestStatus
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BacktestListResponse(BaseModel):
    """List of backtests."""
    backtests: List[BacktestResponse]
    count: int


class BacktestResultsResponse(BaseModel):
    """Backtest results with trades."""
    backtest: BacktestResponse
    trades: List[Trade]
    trade_count: int

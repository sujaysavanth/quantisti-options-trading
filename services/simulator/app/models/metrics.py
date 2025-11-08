"""Pydantic models for backtest performance metrics."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PerformanceMetrics(BaseModel):
    """Performance metrics for a backtest."""
    backtest_id: UUID
    total_trades: int = Field(..., ge=0, description="Total number of trades")
    winning_trades: int = Field(..., ge=0, description="Number of winning trades")
    losing_trades: int = Field(..., ge=0, description="Number of losing trades")
    win_rate: float = Field(..., ge=0, le=100, description="Win rate percentage")
    total_pnl: float = Field(..., description="Total profit/loss in INR")
    avg_pnl_per_trade: float = Field(..., description="Average P&L per trade")
    max_profit: float = Field(..., ge=0, description="Maximum profit in a single trade")
    max_loss: float = Field(..., le=0, description="Maximum loss in a single trade")
    max_drawdown: float = Field(..., le=0, description="Maximum drawdown in INR")
    max_drawdown_pct: float = Field(..., le=0, description="Maximum drawdown percentage")
    sharpe_ratio: Optional[float] = Field(None, description="Sharpe ratio")
    sortino_ratio: Optional[float] = Field(None, description="Sortino ratio")
    profit_factor: Optional[float] = Field(None, ge=0, description="Gross profit / Gross loss")
    avg_holding_days: Optional[float] = Field(None, ge=0, description="Average holding period in days")
    final_capital: float = Field(..., gt=0, description="Final capital after backtest")
    total_return_pct: float = Field(..., description="Total return percentage")
    created_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "backtest_id": "123e4567-e89b-12d3-a456-426614174000",
                "total_trades": 20,
                "winning_trades": 14,
                "losing_trades": 6,
                "win_rate": 70.0,
                "total_pnl": 45000.0,
                "avg_pnl_per_trade": 2250.0,
                "max_profit": 12000.0,
                "max_loss": -8000.0,
                "max_drawdown": -15000.0,
                "max_drawdown_pct": -15.0,
                "sharpe_ratio": 1.85,
                "sortino_ratio": 2.45,
                "profit_factor": 2.8,
                "avg_holding_days": 7.5,
                "final_capital": 145000.0,
                "total_return_pct": 45.0,
                "created_at": "2025-01-15T10:00:00Z"
            }
        }
    }


class MetricsResponse(BaseModel):
    """Metrics response with backtest info."""
    id: UUID
    metrics: PerformanceMetrics

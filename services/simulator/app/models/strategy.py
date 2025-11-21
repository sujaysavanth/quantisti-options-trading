"""Pydantic models for strategy definitions."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class StrategyType(str, Enum):
    """Pre-defined strategy types."""
    LONG_STRADDLE = "LONG_STRADDLE"
    SHORT_STRADDLE = "SHORT_STRADDLE"
    LONG_STRANGLE = "LONG_STRANGLE"
    SHORT_STRANGLE = "SHORT_STRANGLE"
    BULL_CALL_SPREAD = "BULL_CALL_SPREAD"
    BEAR_PUT_SPREAD = "BEAR_PUT_SPREAD"
    BULL_PUT_SPREAD = "BULL_PUT_SPREAD"
    BEAR_CALL_SPREAD = "BEAR_CALL_SPREAD"
    IRON_CONDOR = "IRON_CONDOR"
    IRON_BUTTERFLY = "IRON_BUTTERFLY"
    CALL_RATIO_SPREAD = "CALL_RATIO_SPREAD"
    PUT_RATIO_SPREAD = "PUT_RATIO_SPREAD"
    LONG_CALL_BUTTERFLY = "LONG_CALL_BUTTERFLY"
    LONG_PUT_BUTTERFLY = "LONG_PUT_BUTTERFLY"
    JADE_LIZARD = "JADE_LIZARD"
    REVERSE_JADE_LIZARD = "REVERSE_JADE_LIZARD"
    CALL_RATIO_BACKSPREAD = "CALL_RATIO_BACKSPREAD"
    PUT_RATIO_BACKSPREAD = "PUT_RATIO_BACKSPREAD"
    BWB_CALL = "BWB_CALL"
    LONG_CALENDAR_SPREAD = "LONG_CALENDAR_SPREAD"
    LONG_DIAGONAL_SPREAD = "LONG_DIAGONAL_SPREAD"
    CUSTOM = "CUSTOM"


class PositionAction(str, Enum):
    """Position action (buy or sell)."""
    BUY = "BUY"
    SELL = "SELL"


class OptionType(str, Enum):
    """Option type."""
    CE = "CE"  # Call European
    PE = "PE"  # Put European


class StrategyLeg(BaseModel):
    """Individual leg of a strategy."""
    action: PositionAction = Field(..., description="BUY or SELL")
    option_type: OptionType = Field(..., description="CE or PE")
    strike_offset: int = Field(..., description="Strike offset from ATM in points (e.g., 0, +50, -100)")
    quantity: int = Field(..., gt=0, description="Number of lots")
    leg_order: int = Field(..., ge=1, description="Order of execution")
    expiry_offset: int = Field(0, ge=0, description="Expiry offset in weeks (0=current, 1=next week)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "action": "BUY",
                "option_type": "CE",
                "strike_offset": 0,
                "quantity": 1,
                "leg_order": 1
            }
        }
    }


class StrategyLegResponse(StrategyLeg):
    """Strategy leg with database ID."""
    id: UUID
    strategy_id: UUID
    created_at: datetime


class StrategyCreate(BaseModel):
    """Create a new strategy."""
    name: str = Field(..., min_length=1, max_length=100, description="Strategy name")
    strategy_type: StrategyType = Field(..., description="Type of strategy")
    description: Optional[str] = Field(None, description="Strategy description")
    legs: List[StrategyLeg] = Field(..., min_length=1, description="Strategy legs")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Custom Bull Call Spread",
                "strategy_type": "BULL_CALL_SPREAD",
                "description": "Buy ATM call, sell 100 points OTM call",
                "legs": [
                    {
                        "action": "BUY",
                        "option_type": "CE",
                        "strike_offset": 0,
                        "quantity": 1,
                        "leg_order": 1
                    },
                    {
                        "action": "SELL",
                        "option_type": "CE",
                        "strike_offset": 100,
                        "quantity": 1,
                        "leg_order": 2
                    }
                ]
            }
        }
    }


class StrategyResponse(BaseModel):
    """Strategy response model."""
    id: UUID
    name: str
    strategy_type: StrategyType
    description: Optional[str] = None
    user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    legs: List[StrategyLegResponse] = []

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Long Straddle",
                "strategy_type": "LONG_STRADDLE",
                "description": "Buy ATM call and put",
                "user_id": None,
                "created_at": "2025-01-15T10:00:00Z",
                "updated_at": "2025-01-15T10:00:00Z",
                "legs": []
            }
        }
    }


class StrategyListResponse(BaseModel):
    """List of strategies."""
    strategies: List[StrategyResponse]
    count: int

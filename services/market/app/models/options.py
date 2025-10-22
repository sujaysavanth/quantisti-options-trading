"""Pydantic models for options data."""

from datetime import date
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class OptionType(str, Enum):
    """Option type enumeration."""
    CALL = "CE"  # Call European
    PUT = "PE"   # Put European


class Greeks(BaseModel):
    """Option Greeks."""

    delta: Optional[float] = Field(None, ge=-1, le=1, description="Delta: rate of change of option price w.r.t. underlying")
    gamma: Optional[float] = Field(None, ge=0, description="Gamma: rate of change of delta")
    theta: Optional[float] = Field(None, description="Theta: time decay")
    vega: Optional[float] = Field(None, ge=0, description="Vega: sensitivity to volatility")
    rho: Optional[float] = Field(None, description="Rho: sensitivity to interest rate")

    model_config = {
        "json_schema_extra": {
            "example": {
                "delta": 0.52,
                "gamma": 0.00012,
                "theta": -15.35,
                "vega": 8.74,
                "rho": 5.23
            }
        }
    }


class OptionData(BaseModel):
    """Individual option data."""

    strike: float = Field(..., gt=0, description="Strike price")
    option_type: OptionType
    expiry_date: date

    # Pricing
    price: Optional[float] = Field(None, ge=0, description="Option premium")
    bid: Optional[float] = Field(None, ge=0, description="Bid price")
    ask: Optional[float] = Field(None, ge=0, description="Ask price")

    # Greeks
    greeks: Optional[Greeks] = None

    # Market data
    implied_volatility: Optional[float] = Field(None, ge=0, le=5, description="Implied volatility")
    open_interest: Optional[int] = Field(None, ge=0, description="Open interest")
    volume: Optional[int] = Field(None, ge=0, description="Trading volume")

    # Intrinsic/Extrinsic value (calculated)
    intrinsic_value: Optional[float] = Field(None, ge=0, description="Intrinsic value")
    time_value: Optional[float] = Field(None, ge=0, description="Time value")
    in_the_money: Optional[bool] = Field(None, description="Whether option is ITM")

    model_config = {
        "json_schema_extra": {
            "example": {
                "strike": 21700.0,
                "option_type": "CE",
                "expiry_date": "2024-01-25",
                "price": 156.25,
                "bid": 155.50,
                "ask": 157.00,
                "greeks": {
                    "delta": 0.52,
                    "gamma": 0.00012,
                    "theta": -15.35,
                    "vega": 8.74,
                    "rho": 5.23
                },
                "implied_volatility": 0.1245,
                "open_interest": 145000,
                "volume": 52000,
                "intrinsic_value": 25.50,
                "time_value": 130.75,
                "in_the_money": True
            }
        }
    }


class OptionChainResponse(BaseModel):
    """Option chain response with calls and puts."""

    symbol: str = "NIFTY"
    spot_price: float = Field(..., gt=0, description="Current spot price")
    date: date
    expiry_date: date
    options: List[OptionData]
    total_call_oi: Optional[int] = Field(None, ge=0, description="Total call open interest")
    total_put_oi: Optional[int] = Field(None, ge=0, description="Total put open interest")
    pcr: Optional[float] = Field(None, ge=0, description="Put-Call ratio (OI based)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "NIFTY",
                "spot_price": 21725.50,
                "date": "2024-01-15",
                "expiry_date": "2024-01-25",
                "total_call_oi": 15000000,
                "total_put_oi": 18000000,
                "pcr": 1.20,
                "options": [
                    {
                        "strike": 21700.0,
                        "option_type": "CE",
                        "expiry_date": "2024-01-25",
                        "price": 156.25,
                        "greeks": {
                            "delta": 0.52,
                            "gamma": 0.00012,
                            "theta": -15.35,
                            "vega": 8.74
                        }
                    }
                ]
            }
        }
    }


class OptionChainQuery(BaseModel):
    """Query parameters for option chain."""

    date: Optional[date] = None
    expiry_date: Optional[date] = None
    strike_range: int = 10

    @field_validator('date')
    @classmethod
    def validate_date_not_future(cls, v):
        """Ensure date is not in the future."""
        if v and v > date.today():
            raise ValueError('date cannot be in the future')
        return v

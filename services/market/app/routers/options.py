"""Option chain endpoints."""

import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Path

from .. import market_spec
from ..models.options import OptionChainResponse
from ..services.data_provider import DataProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/options", tags=["options"])
data_provider = DataProvider()


@router.get("/chain", response_model=OptionChainResponse, summary="SPX option chain")
async def get_option_chain(
    date_param: Optional[date] = Query(None, alias="date", description="Trading day to price the chain for (YYYY-MM-DD). Defaults to the latest loaded day"),
    expiry_date: Optional[date] = Query(None, description="Listed expiry (YYYY-MM-DD). Defaults to the nearest expiry with time remaining"),
    strike_range: int = Query(10, ge=1, le=50, description="Number of 5-point strikes above and below the money")
):
    """SPX option chain with prices, implied volatility and Greeks.

    When a collected snapshot of listed quotes exists for the day and expiry
    (`source: snapshot`), prices are real mid quotes and IV/Greeks are
    recomputed from them against a parity-implied forward. Otherwise
    (`source: synthetic`) prices come from Black-Scholes-Merton using the
    day's close, a VIX-based volatility smile, the 3-month T-bill rate and a
    1.3% dividend yield.
    """
    try:
        chain_data = data_provider.generate_option_chain(
            target_date=date_param,
            expiry_date=expiry_date,
            strike_range=strike_range
        )

        if not chain_data:
            if date_param:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data for {date_param}: not a trading day, not loaded, or the expiry has passed."
                )
            raise HTTPException(
                status_code=404,
                detail="No market data loaded. Run scripts/populate_us_data.py first."
            )

        return OptionChainResponse(symbol=market_spec.SYMBOL, **chain_data)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating option chain: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/chain/strikes/{strike}", summary="Get options for specific strike")
async def get_options_by_strike(
    strike: float = Path(..., gt=0, description="Strike price"),
    date_param: Optional[date] = Query(None, alias="date", description="Date for option data"),
    expiry_date: Optional[date] = Query(None, description="Option expiry date")
):
    """Get call and put options for a specific strike price.

    Args:
        strike: Strike price to fetch
        date_param: Date for option data
        expiry_date: Option expiry date

    Returns:
        Call and put options for the specified strike
    """
    try:
        # Get full chain first
        chain_data = data_provider.generate_option_chain(
            target_date=date_param,
            expiry_date=expiry_date,
            strike_range=50  # Large range to ensure we get the strike
        )

        if not chain_data:
            raise HTTPException(status_code=404, detail="No data available")

        # Filter for specific strike
        options = [opt for opt in chain_data['options'] if opt.strike == strike]

        if not options:
            raise HTTPException(
                status_code=404,
                detail=f"Strike {strike} not found within ±{50 * market_spec.STRIKE_STEP} points of the money."
            )

        return {
            "symbol": market_spec.SYMBOL,
            "spot_price": chain_data['spot_price'],
            "date": chain_data['date'],
            "expiry_date": chain_data['expiry_date'],
            "strike": strike,
            "options": options
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching options for strike {strike}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/expiries", summary="Listed expiry dates")
async def get_available_expiries(
    current_date: Optional[date] = Query(None, description="Reference date (defaults to latest loaded day)"),
    days: int = Query(45, ge=1, le=400, description="How many calendar days ahead to list")
):
    """SPX expiries from the reference date, on the NYSE calendar.

    Daily (Mon-Fri) expiries since 2022, Mon/Wed/Fri from 2016, Fridays before
    that; holidays are skipped. Third-Friday expiries are flagged `monthly`.
    """
    try:
        if current_date is None:
            spot_data = data_provider.get_latest_spot_price()
            if not spot_data:
                raise HTTPException(status_code=404, detail="No data available")
            current_date = spot_data['date']

        expiries = [
            {
                "expiry_date": d,
                "days_to_expiry": (d - current_date).days,
                "type": "monthly" if market_spec.is_monthly_expiry(d) else "weekly" if d.weekday() == 4 else "daily",
            }
            for d in market_spec.expiries_between(current_date, current_date + timedelta(days=days))
        ]
        return {"current_date": current_date, "expiries": expiries}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching expiries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

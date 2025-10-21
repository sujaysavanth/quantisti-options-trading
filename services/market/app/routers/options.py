"""Option chain endpoints."""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..models.options import OptionChainResponse, OptionChainQuery
from ..services.data_provider import DataProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/options", tags=["options"])
data_provider = DataProvider()


@router.get("/chain", response_model=OptionChainResponse, summary="Get Nifty option chain")
async def get_option_chain(
    date_param: Optional[date] = Query(None, alias="date", description="Date for option chain (YYYY-MM-DD). If None, uses latest available date"),
    expiry_date: Optional[date] = Query(None, description="Option expiry date (YYYY-MM-DD). If None, uses next monthly expiry"),
    strike_range: int = Query(10, ge=1, le=50, description="Number of strikes above/below ATM to include")
):
    """Get Nifty option chain with calculated prices and Greeks.

    This endpoint generates a complete option chain using Black-Scholes pricing model
    based on historical Nifty data. All option prices and Greeks are calculated using:
    - Historical volatility from the database
    - Black-Scholes-Merton model for European options
    - Risk-free rate: 6.5% (configurable)
    - Dividend yield: 1.2% (configurable)

    Args:
        date_param: Date for which to generate option chain. Defaults to latest available.
        expiry_date: Option expiry date. Defaults to next monthly expiry (last Thursday).
        strike_range: Number of strike prices to include above and below ATM strike.

    Returns:
        Complete option chain with calls and puts, Greeks, and market data
    """
    try:
        # Generate option chain
        chain_data = data_provider.generate_option_chain(
            target_date=date_param,
            expiry_date=expiry_date,
            strike_range=strike_range
        )

        if not chain_data:
            if date_param:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data available for date {date_param}. The option may have expired or no historical data exists."
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail="No historical data found. Please populate the database with Nifty data first."
                )

        return OptionChainResponse(
            symbol="NIFTY",
            **chain_data
        )

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
    strike: float = Query(..., gt=0, description="Strike price"),
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
                detail=f"Strike {strike} not found. Available strikes range from ATM ±{50 * 50} points."
            )

        return {
            "symbol": "NIFTY",
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


@router.get("/expiries", summary="Get available expiry dates")
async def get_available_expiries(
    current_date: Optional[date] = Query(None, description="Reference date (defaults to latest available)")
):
    """Get list of available option expiry dates.

    For Nifty options, this returns the monthly expiry dates (last Thursday of each month)
    for the next 3 months.

    Args:
        current_date: Reference date for calculating expiries

    Returns:
        List of expiry dates
    """
    from datetime import timedelta

    try:
        if current_date is None:
            spot_data = data_provider.get_latest_spot_price()
            if not spot_data:
                raise HTTPException(status_code=404, detail="No data available")
            current_date = spot_data['date']

        # Generate next 3 monthly expiries
        expiries = []
        for i in range(3):
            # Move to next month
            if current_date.month + i > 12:
                year = current_date.year + 1
                month = (current_date.month + i) % 12
            else:
                year = current_date.year
                month = current_date.month + i

            # Get last day of month
            if month == 12:
                last_day = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = date(year, month + 1, 1) - timedelta(days=1)

            # Find last Thursday
            while last_day.weekday() != 3:  # 3 = Thursday
                last_day -= timedelta(days=1)

            if last_day > current_date:
                expiries.append({
                    "expiry_date": last_day,
                    "days_to_expiry": (last_day - current_date).days,
                    "type": "monthly"
                })

        return {
            "current_date": current_date,
            "expiries": expiries
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching expiries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

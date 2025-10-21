"""Nifty market data endpoints."""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..models.market_data import NiftyHistoricalResponse, NiftySpotResponse, HistoricalDataQuery
from ..services.data_provider import DataProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nifty", tags=["nifty"])
data_provider = DataProvider()


@router.get("/spot", response_model=NiftySpotResponse, summary="Get current Nifty spot price")
async def get_spot_price():
    """Get the latest Nifty 50 spot price.

    Returns the most recent closing price from the database.
    """
    try:
        spot_data = data_provider.get_latest_spot_price()

        if not spot_data:
            raise HTTPException(
                status_code=404,
                detail="No historical data found. Please populate the database first."
            )

        # Calculate change from previous day
        # TODO: Implement proper change calculation when we have real-time data
        change = None
        change_percent = None

        return NiftySpotResponse(
            symbol="NIFTY",
            price=spot_data['price'],
            timestamp=datetime.combine(spot_data['date'], datetime.min.time()),
            change=change,
            change_percent=change_percent,
            volume=spot_data.get('volume')
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching spot price: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/historical", response_model=NiftyHistoricalResponse, summary="Get historical Nifty data")
async def get_historical_data(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)")
):
    """Get historical Nifty OHLCV data for a date range.

    Args:
        start_date: Start date for historical data
        end_date: End date for historical data

    Returns:
        Historical candle data with OHLCV and volatility
    """
    try:
        # Validate dates
        if end_date < start_date:
            raise HTTPException(
                status_code=400,
                detail="end_date must be greater than or equal to start_date"
            )

        if start_date > date.today():
            raise HTTPException(
                status_code=400,
                detail="start_date cannot be in the future"
            )

        # Limit date range to prevent excessive queries
        days_diff = (end_date - start_date).days
        if days_diff > 365 * 5:  # 5 years max
            raise HTTPException(
                status_code=400,
                detail="Date range cannot exceed 5 years"
            )

        # Fetch data
        candles = data_provider.get_historical_data(start_date, end_date)

        if not candles:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for date range {start_date} to {end_date}"
            )

        return NiftyHistoricalResponse(
            symbol="NIFTY",
            data=candles,
            count=len(candles),
            start_date=start_date,
            end_date=end_date
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching historical data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/candles/{period}", summary="Get Nifty candles for predefined period")
async def get_candles_by_period(
    period: str = Query(..., regex="^(1d|1w|1m|3m|6m|1y|5y)$", description="Time period")
):
    """Get historical candles for a predefined period.

    Args:
        period: One of: 1d, 1w, 1m, 3m, 6m, 1y, 5y

    Returns:
        Historical candle data
    """
    from datetime import timedelta

    # Map period to days
    period_map = {
        "1d": 1,
        "1w": 7,
        "1m": 30,
        "3m": 90,
        "6m": 180,
        "1y": 365,
        "5y": 365 * 5
    }

    days = period_map.get(period)
    if not days:
        raise HTTPException(status_code=400, detail=f"Invalid period: {period}")

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    try:
        candles = data_provider.get_historical_data(start_date, end_date)

        if not candles:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for period {period}"
            )

        return NiftyHistoricalResponse(
            symbol="NIFTY",
            data=candles,
            count=len(candles),
            start_date=start_date,
            end_date=end_date
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching candles for period {period}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

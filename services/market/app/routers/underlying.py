"""Underlying index (SPX) market data endpoints."""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import JSONResponse

from .. import market_spec
from ..models.market_data import UnderlyingHistoryResponse, UnderlyingSpotResponse
from ..services.data_provider import DataProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/underlying", tags=["underlying"])
data_provider = DataProvider()


@router.get("/spot", response_model=UnderlyingSpotResponse, summary="Latest SPX close")
async def get_spot_price():
    """Latest close of the underlying, with the change from the previous close."""
    try:
        spot_data = data_provider.get_latest_spot_price()

        if not spot_data:
            raise HTTPException(
                status_code=404,
                detail="No historical data found. Please populate the database first."
            )

        return UnderlyingSpotResponse(
            symbol=market_spec.SYMBOL,
            price=spot_data['price'],
            timestamp=market_spec.session_close(spot_data['date']),
            change=round(spot_data['change'], 2) if spot_data['change'] is not None else None,
            change_percent=round(spot_data['change_percent'], 3) if spot_data['change_percent'] is not None else None,
            volume=spot_data.get('volume')
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching spot price: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/historical", response_model=UnderlyingHistoryResponse, summary="Historical SPX daily candles")
async def get_historical_data(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)")
):
    """Daily OHLCV for the underlying over a date range.

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

        return UnderlyingHistoryResponse(
            symbol=market_spec.SYMBOL,
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


@router.get("/candles/{period}", response_model=UnderlyingHistoryResponse, summary="SPX candles for a predefined period")
async def get_candles_by_period(
    period: str = Path(..., pattern="^(1d|1w|1m|3m|6m|1y|5y)$", description="Time period")
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

        return UnderlyingHistoryResponse(
            symbol=market_spec.SYMBOL,
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


@router.get("/vix", summary="CBOE VIX daily closes")
async def get_vix_history(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)")
):
    """VIX closes (30-day implied volatility of SPX, in vol points) for a date range."""
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be greater than or equal to start_date")
    try:
        data = data_provider.get_vix_history(start_date, end_date)
    except Exception as e:
        logger.error(f"Error fetching VIX history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"symbol": "VIX", "count": len(data), "data": data}

"""Feature computation and retrieval endpoints."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from ..models.features import (
    FeatureComputeRequest,
    FeatureResponse,
    FeatureListResponse,
    WeeklyFeatures
)
from ..services.feature_service import FeatureService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/features", tags=["features"])

# Global service instance
feature_service = FeatureService()


@router.post("/compute", response_model=FeatureResponse, summary="Compute features for a week")
async def compute_features(request: FeatureComputeRequest):
    """Compute all features for a given week.

    Args:
        request: Feature computation request

    Returns:
        Computed features
    """
    try:
        # Check if features already exist
        if not request.force_recompute:
            existing = feature_service.get_features(
                request.symbol,
                request.week_start_date
            )
            if existing:
                return FeatureResponse(
                    features=existing,
                    message="Features retrieved from cache"
                )

        # Compute new features
        features = await feature_service.compute_weekly_features(
            request.symbol,
            request.week_start_date
        )

        if not features:
            raise HTTPException(
                status_code=500,
                detail="Failed to compute features. Check market data availability and logs."
            )

        # Save to database
        saved = feature_service.save_features(features)

        if not saved:
            logger.warning("Features computed but failed to save to database")

        return FeatureResponse(
            features=features,
            message="Features computed and saved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in compute_features: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/weekly/{symbol}/{date}",
           response_model=FeatureResponse,
           summary="Get features for specific week")
async def get_weekly_features(
    symbol: str,
    date: datetime,
):
    """Get features for a specific week.

    Args:
        symbol: Underlying symbol (e.g., NIFTY)
        date: Week start date

    Returns:
        Weekly features
    """
    try:
        features = feature_service.get_features(symbol, date)

        if not features:
            raise HTTPException(
                status_code=404,
                detail=f"Features not found for {symbol} on {date}. Try computing them first with POST /v1/features/compute"
            )

        return FeatureResponse(
            features=features,
            message="Features retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting features: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/latest/{symbol}",
           response_model=FeatureResponse,
           summary="Get latest features for symbol")
async def get_latest_features(symbol: str):
    """Get most recently computed features for a symbol.

    Args:
        symbol: Underlying symbol

    Returns:
        Latest features
    """
    try:
        features = feature_service.get_latest_features(symbol)

        if not features:
            raise HTTPException(
                status_code=404,
                detail=f"No features found for {symbol}. Compute some features first."
            )

        return FeatureResponse(
            features=features,
            message="Latest features retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest features: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/backfill",
            summary="Backfill historical features")
async def backfill_features(
    background_tasks: BackgroundTasks,
    symbol: str = Query("NIFTY", description="Symbol to backfill"),
    start_date: datetime = Query(..., description="Start date"),
    end_date: datetime = Query(..., description="End date"),
    interval_days: int = Query(7, description="Interval in days (default 7 for weekly)")
):
    """Compute features for a date range (backfill historical data).

    This runs in the background and computes features for each week in the range.

    Args:
        symbol: Underlying symbol
        start_date: Start date
        end_date: End date
        interval_days: Days between feature computations (7 for weekly)

    Returns:
        Status message
    """
    try:
        # Validate dates
        if end_date < start_date:
            raise HTTPException(
                status_code=400,
                detail="end_date must be after start_date"
            )

        # Calculate number of weeks
        days_diff = (end_date.date() - start_date.date()).days
        num_weeks = days_diff // interval_days

        if num_weeks > 260:  # ~5 years of weekly data
            raise HTTPException(
                status_code=400,
                detail="Date range too large. Maximum 260 weeks (~5 years)."
            )

        # Add backfill task to background
        background_tasks.add_task(
            run_backfill,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval_days=interval_days
        )

        return {
            "status": "started",
            "message": f"Backfill started for {symbol} from {start_date.date()} to {end_date.date()}",
            "estimated_weeks": num_weeks,
            "note": "Check logs for progress. Features will be available as they're computed."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in backfill: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def run_backfill(symbol: str, start_date: datetime, end_date: datetime, interval_days: int = 7):
    """Background task to backfill features.

    Args:
        symbol: Symbol to backfill
        start_date: Start date
        end_date: End date
        interval_days: Days between computations
    """
    logger.info(f"Starting backfill for {symbol} from {start_date} to {end_date}")

    current_date = start_date
    success_count = 0
    failure_count = 0

    while current_date <= end_date:
        try:
            logger.info(f"Computing features for {symbol} week {current_date.date()}")

            # Compute features
            features = await feature_service.compute_weekly_features(symbol, current_date)

            if features:
                # Save features
                saved = feature_service.save_features(features)
                if saved:
                    success_count += 1
                    logger.info(f"✓ Saved features for {current_date.date()}")
                else:
                    failure_count += 1
                    logger.error(f"✗ Failed to save features for {current_date.date()}")
            else:
                failure_count += 1
                logger.error(f"✗ Failed to compute features for {current_date.date()}")

        except Exception as e:
            failure_count += 1
            logger.error(f"Error processing {current_date.date()}: {e}")

        # Move to next interval
        current_date = current_date + timedelta(days=interval_days)

    logger.info(f"Backfill complete: {success_count} succeeded, {failure_count} failed")

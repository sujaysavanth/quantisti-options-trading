"""Feature computation and retrieval endpoints."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
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
                detail="Failed to compute features. Check market data availability."
            )

        # Save to database
        feature_service.save_features(features)

        return FeatureResponse(
            features=features,
            message="Features computed and saved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in compute_features: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
                detail=f"Features not found for {symbol} on {date}. Try computing them first."
            )

        return FeatureResponse(
            features=features,
            message="Features retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting features: {e}")
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
        # TODO: Implement get_latest_features in service
        # features = feature_service.get_latest_features(symbol)

        raise HTTPException(
            status_code=501,
            detail="Not implemented yet. Use /weekly/{symbol}/{date} endpoint."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest features: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/backfill",
            summary="Backfill historical features")
async def backfill_features(
    symbol: str = Query(..., description="Symbol to backfill"),
    start_date: datetime = Query(..., description="Start date"),
    end_date: datetime = Query(..., description="End date")
):
    """Compute features for a date range (backfill historical data).

    Args:
        symbol: Underlying symbol
        start_date: Start date
        end_date: End date

    Returns:
        Status message
    """
    try:
        # TODO: Implement backfill logic
        # This should iterate through weeks and compute features for each

        raise HTTPException(
            status_code=501,
            detail="Backfill not implemented yet. This will be used for training data generation."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in backfill: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

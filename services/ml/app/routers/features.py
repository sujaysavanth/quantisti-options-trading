"""Weekly feature endpoints.

Every week is built in one pass from underlying_daily / vix_daily / rates_daily (app/dataset/), so
"computing" any week rebuilds them all: about a second, and rolling windows stay consistent.
"""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from ..models.features import FeatureComputeRequest, FeatureResponse
from ..services.feature_service import SUPPORTED_SYMBOLS, FeatureService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/features", tags=["features"])
feature_service = FeatureService()


def _check_symbol(symbol: str) -> None:
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Only {', '.join(SUPPORTED_SYMBOLS)} is supported")


def _found(features, what: str) -> FeatureResponse:
    if features is None:
        raise HTTPException(status_code=404, detail=f"No features for {what}. Build them with POST /v1/features/backfill")
    return FeatureResponse(features=features, message="Features retrieved successfully")


@router.post("/compute", response_model=FeatureResponse, summary="Features for one week")
def compute_features(request: FeatureComputeRequest):
    """The week containing `week_start_date`, rebuilding all weeks first if it isn't stored (or if forced)."""
    _check_symbol(request.symbol)
    stored = None if request.force_recompute else feature_service.get_features(request.symbol, request.week_start_date)
    if stored is not None:
        return FeatureResponse(features=stored, message="Features retrieved from the database")
    feature_service.rebuild(request.symbol)
    features = feature_service.get_features(request.symbol, request.week_start_date)
    if features is None:
        raise HTTPException(status_code=404, detail=(
            f"No complete week contains {request.week_start_date}: before the data starts, "
            "or the week hasn't closed yet"))
    return FeatureResponse(features=features, message="Features computed and saved")


@router.get("/weekly/{symbol}/{day}", response_model=FeatureResponse, summary="Features for a specific week")
def get_weekly_features(symbol: str, day: date):
    """The stored week containing `day` (any day of the week)."""
    _check_symbol(symbol)
    return _found(feature_service.get_features(symbol, day), f"{symbol} in the week of {day}")


@router.get("/latest/{symbol}", response_model=FeatureResponse, summary="Latest complete week")
def get_latest_features(symbol: str):
    _check_symbol(symbol)
    return _found(feature_service.get_latest_features(symbol), symbol)


@router.post("/backfill", summary="Build every week from 2010 to the last complete one")
def backfill_features(symbol: str = Query("SPX", description="Only SPX is loaded")):
    """Rebuild all weekly features and next-week labels in one pass and store them. Safe to re-run."""
    _check_symbol(symbol)
    return feature_service.rebuild(symbol)

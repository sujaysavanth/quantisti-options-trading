"""Live strategy suggestions based on market-stream quotes."""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_market_stream_client
from ..services.market_stream_client import MarketStreamClient
from ..services.quote_pricing import available_expiries, select_expiry
from ..services.strategy_builder import build_strategies_from_quote
from ..models.strategy_live import StrategyInstance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/strategies-live", tags=["strategies"])


@router.get("/", response_model=list[StrategyInstance])
async def get_live_strategies(
    symbol: str = Query(default="SPX"),
    expiry: Optional[date] = Query(default=None, description="Expiry to build on; defaults to the quote's default expiry"),
    stream_client: MarketStreamClient = Depends(get_market_stream_client)
):
    quote = await stream_client.get_quote(symbol)
    if not quote:
        raise HTTPException(status_code=404, detail=f"No live quote for {symbol}. Start the ingest and stream-bridge services.")

    requested = expiry.isoformat() if expiry else None
    if requested and select_expiry(quote, requested) is None:
        raise HTTPException(status_code=404,
                            detail=f"No quotes for expiry {requested}. Available: {', '.join(available_expiries(quote))}")
    return build_strategies_from_quote(quote, requested)

"""Live strategy suggestions based on market-stream quotes."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_market_stream_client
from ..services.market_stream_client import MarketStreamClient
from ..services.strategy_builder import build_strategies_from_quote
from ..models.strategy_live import StrategyInstance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/strategies-live", tags=["strategies"])


@router.get("/", response_model=list[StrategyInstance])
async def get_live_strategies(
    symbol: str = Query(default="NIFTY"),
    stream_client: MarketStreamClient = Depends(get_market_stream_client)
):
    quote = await stream_client.get_quote(symbol)
    if not quote:
        raise HTTPException(status_code=404, detail=f"No live quote for {symbol}. Start collectors.")

    strategies = build_strategies_from_quote(quote)
    return strategies

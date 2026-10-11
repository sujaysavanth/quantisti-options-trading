"""Risk endpoints for the paper portfolio.

    GET /v1/risk/greeks    delta, gamma, vega, theta in dollars: totals, by expiry and per position
"""

from fastapi import APIRouter, HTTPException

from .. import clients, market_spec
from ..services.exposure import portfolio_greeks

router = APIRouter(prefix="/v1/risk", tags=["risk"])


async def _inputs():
    positions = await clients.positions()
    if positions is None:
        raise HTTPException(status_code=502, detail="Portfolio service unavailable: positions can't be read.")
    quote = await clients.quote()
    if not quote or not quote.get("last_price"):
        raise HTTPException(status_code=503, detail="No live SPX quote on market-stream.")
    rate = clients.latest_rate()
    return positions, quote, (rate if rate is not None else market_spec.FALLBACK_RATE)


@router.get("/greeks", summary="Greeks of the open paper positions")
async def risk_greeks():
    positions, quote, rate = await _inputs()
    return portfolio_greeks(positions, quote, rate)

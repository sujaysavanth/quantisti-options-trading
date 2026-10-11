"""Risk endpoints for the paper portfolio.

    GET /v1/risk/greeks    delta, gamma, vega, theta in dollars: totals, by expiry and per position
    GET /v1/risk/stress    P&L and capital after SPX x IV x time shocks, and replays of the largest SPX days
"""

from fastapi import APIRouter, HTTPException, Query

from .. import clients, market_spec
from ..services import stress as st
from ..services.exposure import Market, portfolio_greeks

router = APIRouter(prefix="/v1/risk", tags=["risk"])


async def _market():
    quote = await clients.quote()
    if not quote or not quote.get("last_price"):
        raise HTTPException(status_code=503, detail="No live SPX quote on market-stream.")
    rate = clients.latest_rate()
    return quote, (rate if rate is not None else market_spec.FALLBACK_RATE)


async def _inputs():
    positions = await clients.positions()
    if positions is None:
        raise HTTPException(status_code=502, detail="Portfolio service unavailable: positions can't be read.")
    return (positions, *await _market())


@router.get("/greeks", summary="Greeks of the open paper positions")
async def risk_greeks():
    positions, quote, rate = await _inputs()
    return portfolio_greeks(positions, quote, rate)


@router.get("/stress", summary="Stress scenarios for the open paper trades")
async def risk_stress(falls: int = Query(10, ge=0, le=50), rises: int = Query(5, ge=0, le=50)):
    trades, account = await clients.open_trades(), await clients.account()
    if trades is None or account is None:
        raise HTTPException(status_code=502, detail="Simulator unavailable: open trades can't be read.")
    quote, rate = await _market()
    market = Market(quote, rate)
    legs, unpriced = st.book(trades, market)

    days = clients.extreme_days(falls, rises) or []
    grid, history = st.grid(), st.historical(days)
    scenarios = grid + history
    revalued = [st.revalue(legs, len(trades), rate, s) for s in scenarios]
    if trades:
        held = await clients.capital_held(st.capital_request(trades, market.spot, scenarios, [m for _, m in revalued]))
    else:
        held = [0.0] * len(scenarios)
    rows = st.results(scenarios, [p for p, _ in revalued], held or [None] * len(scenarios), account)
    return {
        "spot": market.spot, "rate": rate, "quoted_at": market.quoted_at, "open_trades": len(trades),
        "account": {k: account[k] for k in ("account_value", "capital_held", "available")},
        "axes": {"spx_moves": st.SPX_MOVES, "iv_shifts": st.IV_SHIFTS, "horizons_days": st.HORIZONS},
        "grid": rows[:len(grid)], "historical": rows[len(grid):],
        "summary": {"grid": st.summary(rows[:len(grid)]), "historical": st.summary(rows[len(grid):])},
        "capital_available": held is not None, "history_available": bool(days), "unpriced": unpriced,
    }

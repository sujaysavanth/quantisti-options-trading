"""Risk endpoints for the paper portfolio.

    GET /v1/risk/greeks    delta, gamma, vega, theta in dollars: totals, by expiry and per position
    GET  /v1/risk/stress        P&L and capital after SPX x IV x time shocks, and replays of the largest SPX days
    GET  /v1/risk/var           1-day VaR and expected shortfall now, 95% / 99%, three methods
    GET  /v1/risk/var/history   stored VaR per session with the realised next-day P&L, breaches, Kupiec, Christoffersen
    POST /v1/risk/var/run       store this session's VaR if it is due (the background task does this after each close)
    POST /v1/risk/what-if       Greeks, VaR and stress of the book now and with a candidate trade added, and its capital
"""

from datetime import date, datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .. import clients, market_spec
from ..services import stress as st
from ..services import var as var_maths
from ..services import var_run
from ..services import whatif
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


@router.get("/var", summary="1-day VaR and expected shortfall of the open paper trades")
async def risk_var():
    result = await var_run.current()
    if result is None:
        raise HTTPException(status_code=503, detail="Simulator or live SPX quote unavailable.")
    if not result["methods"]:
        raise HTTPException(status_code=503, detail="No SPX history in underlying_daily.")
    return result


@router.get("/var/history", summary="Stored VaR, realised next-day P&L and the backtests")
async def risk_var_history(request: Request, start: Optional[date] = None, end: Optional[date] = None):
    rows = request.app.state.var_store.list(start, end)
    closes = await clients.portfolio_closes()
    realised = var_run.realised_next(closes or [])
    for r in rows:
        r["realised_next_day"] = realised.get(r["session"])
        r["breach"] = None if r["realised_next_day"] is None else -r["realised_next_day"] > r["var"]
    return {"rows": rows, "portfolio_available": closes is not None, **var_maths.backtest(rows, realised),
            "note": "Realised P&L is the change between consecutive close snapshots, so it also includes trades "
                    "opened or closed that day. Kupiec and Christoffersen need ~250 days at 99% to say much."}


@router.post("/var/run", summary="Store this session's VaR if it is due")
async def risk_var_run(request: Request):
    return {"due": var_run.due_close(datetime.now(timezone.utc)),
            "rows_written": await var_run.store_due(request.app.state.var_store)}


class CandidateLeg(BaseModel):
    strike: float
    option_type: Literal["CALL", "PUT"]
    expiry: date
    side: Literal["BUY", "SELL"]
    quantity: int = Field(1, gt=0)


class Candidate(BaseModel):
    legs: List[CandidateLeg] = Field(min_length=1)


@router.post("/what-if", summary="The book's risk with a candidate trade added")
async def risk_what_if(candidate: Candidate):
    x = await var_run.gather()
    if x is None:
        raise HTTPException(status_code=503, detail="Simulator or live SPX quote unavailable.")
    trade = whatif.candidate_trade([leg.model_dump() for leg in candidate.legs], x.market)
    if "errors" in trade:
        raise HTTPException(status_code=422, detail="Can't price: " + "; ".join(trade["errors"]))
    days = clients.extreme_days(10, 5) or []
    before = whatif.measure(x.trades, x.market, x.rate, x.moves, x.sigma_now, days)
    after = whatif.measure([*x.trades, trade], x.market, x.rate, x.moves, x.sigma_now, days)
    cap = await clients.capital_scenarios(st.capital_request(
        [trade], x.market.spot, [st.Scenario("now", 0.0, 0.0, 0)], [[[leg["entry_price"] for leg in trade["legs"]]]]))
    held = cap[0]["by_trade"][0] if cap else {"amount": None, "basis": None}
    return {
        "spot": x.market.spot, "quoted_at": x.market.quoted_at, "open_trades": len(x.trades),
        "candidate": trade["legs"],
        "capital": whatif.capital_check(held["amount"], held["basis"], float(x.account["available"])),
        "metrics": whatif.compare(before, after),
        "var_method": "filtered_historical",
    }

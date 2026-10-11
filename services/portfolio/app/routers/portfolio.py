"""Portfolio endpoints.

    GET  /v1/portfolio/positions         open positions netted by contract, plus the open trades behind them
    GET  /v1/portfolio/equity            stored snapshots (?kind=close|intraday, ?start=, ?end=, ?positions=true)
    GET  /v1/portfolio/trades            trade history (?status=closed|open|all, default closed)
    GET  /v1/portfolio/trades.csv        the same history, one row per leg
    POST /v1/portfolio/snapshots/run     take the snapshot due now, if any (the background task does this every minute)
"""

from datetime import date, datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from ..clients import MarketStreamClient, SimulatorClient
from ..services import positions as views
from ..services.schedule import due
from ..services.snapshots import SnapshotStore, take_due

router = APIRouter(prefix="/v1/portfolio", tags=["portfolio"])


def _store(request: Request) -> SnapshotStore:
    return request.app.state.snapshot_store  # type: ignore[attr-defined]


async def _trades() -> list:
    trades = await SimulatorClient().orders()
    if trades is None:
        raise HTTPException(status_code=502, detail="Simulator unavailable: paper trades can't be read.")
    return trades


def _filter(trades: list, status: str) -> list:
    return trades if status == "all" else [t for t in trades if t["status"] == status]


@router.get("/positions", summary="Open positions netted by contract")
async def positions():
    open_ = _filter(await _trades(), "open")
    net = views.net_positions(open_)
    return {
        "as_of": datetime.now(timezone.utc),
        "positions": net,
        "unrealised_pnl": sum(float(t["pnl"]) for t in open_),
        "trades": [{"id": t["id"], "nickname": t.get("nickname"), "expiry": t.get("expiry"), "pnl": t["pnl"],
                    "capital_held": t.get("capital_held"), "legs": len(t["legs"])} for t in open_],
    }


@router.get("/equity", summary="Stored portfolio snapshots (the equity curve)")
def equity(request: Request, kind: Optional[Literal["close", "intraday"]] = None, start: Optional[date] = None,
           end: Optional[date] = None, positions: bool = False):
    rows = _store(request).list(kind, start, end, positions)
    return {"count": len(rows), "snapshots": rows}


@router.get("/trades", summary="Trade history")
async def trades(status: Literal["closed", "open", "all"] = "closed"):
    return _filter(await _trades(), status)


@router.get("/trades.csv", summary="Trade history as CSV, one row per leg")
async def trades_csv(status: Literal["closed", "open", "all"] = "closed"):
    body = views.to_csv(views.trade_rows(_filter(await _trades(), status)))
    return Response(body, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="paper-trades-{status}.csv"'})


@router.post("/snapshots/run", summary="Take the snapshot due now, if any")
async def run_snapshot(request: Request):
    now = datetime.now(timezone.utc)
    slot = due(now)
    snap = await take_due(_store(request), SimulatorClient(), MarketStreamClient(), now)
    return {"due": slot, "taken": snap is not None,
            "snapshot": {k: v for k, v in vars(snap).items() if k != "positions"} if snap else None}

"""Paper trading endpoints and the paper account.

    POST   /v1/paper/orders              open a trade at the mids (refused if it needs more capital than is available)
    GET    /v1/paper/orders              every trade: open ones marked to the live mids, closed ones at their exits
    POST   /v1/paper/orders/{id}/close   close an open trade now at the mids
    DELETE /v1/paper/orders/{id}         remove an open trade entered by mistake (closed trades are kept)
    GET    /v1/paper/account             $30,000 start, realised / unrealised / total P&L, capital held, available

Open trades are settled SETTLE_BEFORE their expiry's close by settle_due(), which main.py runs every minute.
Rules: app/services/paper_settlement.py.
"""

import logging
from datetime import date, datetime, timezone
from typing import List, Optional, Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..config import get_settings
from ..dependencies import get_market_stream_client, get_paper_store
from ..models.paper import PaperAccount, PaperLegInput, PaperLegState, PaperTradeCreate, PaperTradeResponse
from ..services import paper_settlement as rules
from ..services.market_stream_client import MarketStreamClient
from ..services.paper_store import PaperTradeStore, StoredLeg, StoredTrade
from ..services.quote_pricing import leg_price

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/paper", tags=["paper-trading"])

settings = get_settings()
MULTIPLIER = settings.CONTRACT_MULTIPLIER


def _match_quote_leg(quote: dict, leg: PaperLegInput | StoredLeg):
    legs = quote.get("legs", [])
    identifier = getattr(leg, "identifier", None)
    expiry = getattr(leg, "expiry", None)
    if isinstance(expiry, str):
        expiry_iso = expiry
    else:
        expiry_iso = expiry.isoformat() if expiry else None

    for q_leg in legs:
        if identifier and q_leg.get("identifier") == identifier:
            return q_leg
    for q_leg in legs:
        if (
            expiry_iso
            and float(q_leg.get("strike", 0)) == float(getattr(leg, "strike"))
            and q_leg.get("option_type") == getattr(leg, "option_type")
            and q_leg.get("expiry") == expiry_iso
        ):
            return q_leg
    return None


def _price_from_quote(q_leg: dict) -> float:
    # Enter and mark at the bid/ask mid; the last trade is only a fallback.
    return leg_price(q_leg)


def _positions(legs: Sequence[StoredLeg], marks: Optional[Sequence[Optional[float]]] = None) -> List[rules.Position]:
    """Rule positions at entry prices, with current mids (`marks`) where known."""
    return [rules.Position(leg.strike, leg.option_type, leg.side, leg.quantity, leg.entry_price or 0.0,
                           marks[i] if marks is not None else None) for i, leg in enumerate(legs)]


def _current_prices(trade: StoredTrade, quote: dict) -> List[Optional[float]]:
    prices = []
    for leg in trade.legs:
        q_leg = _match_quote_leg(quote, leg) if quote else None
        prices.append(_price_from_quote(q_leg) if q_leg else None)
    return prices


def build_response(trade: StoredTrade, quote: dict) -> PaperTradeResponse:
    closed = trade.status == "closed"
    prices = [leg.exit_price for leg in trade.legs] if closed else _current_prices(trade, quote)
    leg_states: List[PaperLegState] = []
    entry_total = 0.0
    current_total = 0.0
    for leg, current_price in zip(trade.legs, prices):
        entry_price = leg.entry_price or 0.0
        side_mult = 1 if leg.side == "BUY" else -1
        entry_value = entry_price * leg.quantity * MULTIPLIER * side_mult
        current_value = current_price * leg.quantity * MULTIPLIER * side_mult if current_price is not None else entry_value
        entry_total += entry_value
        current_total += current_value
        leg_states.append(PaperLegState(
            identifier=leg.identifier, strike=leg.strike, option_type=leg.option_type,  # type: ignore[arg-type]
            expiry=leg.expiry, quantity=leg.quantity, side=leg.side,  # type: ignore[arg-type]
            entry_price=entry_price or None, current_price=None if closed else current_price,
            exit_price=leg.exit_price, pnl=current_value - entry_value))

    expiry = date.fromisoformat(trade.expiry) if trade.expiry else None
    held = None
    if not closed and quote.get("last_price"):
        held = rules.capital_held(_positions(trade.legs, prices), float(quote["last_price"]))
    return PaperTradeResponse(
        id=trade.id, symbol=trade.symbol, nickname=trade.nickname, created_at=trade.created_at,
        entry_notional=entry_total, current_notional=current_total, pnl=current_total - entry_total, legs=leg_states,
        status=trade.status, expiry=expiry, settles_at=rules.settle_time(expiry) if expiry and not closed else None,  # type: ignore[arg-type]
        closed_at=trade.closed_at, close_reason=trade.close_reason,
        capital_held=held["amount"] if held else None, capital_basis=held["basis"] if held else None)


def account_summary(store: PaperTradeStore, trades: List[PaperTradeResponse]) -> PaperAccount:
    starting = store.starting_balance()
    realised = sum(t.pnl for t in trades if t.status == "closed")
    unrealised = sum(t.pnl for t in trades if t.status == "open")
    held = sum(t.capital_held or 0.0 for t in trades if t.status == "open")
    return PaperAccount(
        starting_balance=starting, realised_pnl=realised, unrealised_pnl=unrealised, total_pnl=realised + unrealised,
        account_value=starting + realised + unrealised, capital_held=held, available=starting + realised - held,
        open_trades=sum(t.status == "open" for t in trades), closed_trades=sum(t.status == "closed" for t in trades))


async def _all_responses(store: PaperTradeStore, quote_client: MarketStreamClient) -> List[PaperTradeResponse]:
    trades = store.list_trades()
    quotes: dict = {}
    for symbol in {t.symbol for t in trades if t.status == "open"}:
        quotes[symbol] = await quote_client.get_quote(symbol) or {}
    return [build_response(t, quotes.get(t.symbol, {})) for t in trades]


@router.post("/orders", response_model=PaperTradeResponse, summary="Create paper trade")
async def create_paper_order(
    payload: PaperTradeCreate,
    store: PaperTradeStore = Depends(get_paper_store),
    quote_client: MarketStreamClient = Depends(get_market_stream_client)
):
    quote = await quote_client.get_quote(payload.symbol)
    if not quote:
        raise HTTPException(status_code=400, detail=f"No quote available for {payload.symbol}. Start collectors.")

    stored_legs: List[StoredLeg] = []
    for leg in payload.legs:
        quote_leg = _match_quote_leg(quote, leg)
        if leg.identifier and not quote_leg:
            raise HTTPException(status_code=400, detail=f"Identifier {leg.identifier} not found in live quotes.")
        entry_price = _price_from_quote(quote_leg) if quote_leg else 0.0
        stored_legs.append(StoredLeg(
            identifier=leg.identifier or (quote_leg.get("identifier") if quote_leg else None), strike=leg.strike,
            option_type=leg.option_type, expiry=leg.expiry.isoformat(), quantity=leg.quantity, side=leg.side,
            entry_price=entry_price))

    expiry = min(date.fromisoformat(leg.expiry) for leg in stored_legs)
    if rules.settlement_mode(expiry, datetime.now(timezone.utc)) is not None:
        raise HTTPException(status_code=400, detail=f"Too late: trades on the {expiry} expiry settle "
                                                    f"{int(rules.SETTLE_BEFORE.total_seconds() // 60)} minutes before its close.")
    need = rules.capital_held(_positions(stored_legs), float(quote.get("last_price") or 0.0))
    account = account_summary(store, await _all_responses(store, quote_client))
    if need["amount"] > account.available + 1e-6:
        raise HTTPException(status_code=400, detail=(
            f"Not enough capital: this trade holds ${need['amount']:,.0f} ({need['basis']}), "
            f"available ${account.available:,.0f}."))

    trade = store.add_trade(payload.symbol, payload.nickname, stored_legs)
    return build_response(trade, quote)


@router.get("/orders", response_model=List[PaperTradeResponse], summary="List paper trades")
async def list_paper_orders(
    store: PaperTradeStore = Depends(get_paper_store),
    quote_client: MarketStreamClient = Depends(get_market_stream_client)
):
    return await _all_responses(store, quote_client)


@router.get("/account", response_model=PaperAccount, summary="Paper account: balance, P&L, capital held, available")
async def paper_account(
    store: PaperTradeStore = Depends(get_paper_store),
    quote_client: MarketStreamClient = Depends(get_market_stream_client)
):
    return account_summary(store, await _all_responses(store, quote_client))


@router.get("/orders/{trade_id}", response_model=PaperTradeResponse, summary="Get trade by ID")
async def get_paper_order(
    trade_id: UUID,
    store: PaperTradeStore = Depends(get_paper_store),
    quote_client: MarketStreamClient = Depends(get_market_stream_client)
):
    trade = store.get_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    quote = await quote_client.get_quote(trade.symbol) or {}
    return build_response(trade, quote)


@router.post("/orders/{trade_id}/close", response_model=PaperTradeResponse, summary="Close a paper trade now")
async def close_paper_order(
    trade_id: UUID,
    store: PaperTradeStore = Depends(get_paper_store),
    quote_client: MarketStreamClient = Depends(get_market_stream_client)
):
    trade = store.get_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status != "open":
        raise HTTPException(status_code=409, detail="Trade is already closed")
    quote = await quote_client.get_quote(trade.symbol) or {}
    exits = _exit_prices_from_quote(trade, quote)
    if exits is None:
        raise HTTPException(status_code=400, detail="No live quote to close against; try again when quotes arrive.")
    store.close_trade(trade_id, exits, "closed manually at the mids", datetime.now(timezone.utc))
    return build_response(store.get_trade(trade_id), {})  # type: ignore[arg-type]


@router.delete("/orders/{trade_id}", status_code=204, summary="Delete an open paper trade")
async def delete_paper_order(
    trade_id: UUID,
    store: PaperTradeStore = Depends(get_paper_store)
):
    trade = store.get_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status != "open" or not store.delete_trade(trade_id):
        raise HTTPException(status_code=409, detail="Closed trades are kept: their P&L is part of the account")


# --- settlement ---------------------------------------------------------------------------------------------

def _exit_prices_from_quote(trade: StoredTrade, quote: dict) -> Optional[List[float]]:
    """Each leg's mid; a leg missing from the quote is valued at intrinsic against the quote's index price."""
    spot = quote.get("last_price")
    if not quote or not spot:
        return None
    prices = []
    for leg, mid in zip(trade.legs, _current_prices(trade, quote)):
        prices.append(mid if mid is not None else rules.intrinsic(leg.option_type, leg.strike, float(spot)))
    return prices


async def settle_due(store: PaperTradeStore, quote_client: MarketStreamClient, now: Optional[datetime] = None) -> int:
    """Close every open trade whose settlement time has come. Returns how many were closed."""
    now = now or datetime.now(timezone.utc)
    closed = 0
    for trade in store.list_trades(status="open"):
        if not trade.expiry:
            continue
        expiry = date.fromisoformat(trade.expiry)
        mode = rules.settlement_mode(expiry, now)
        if mode is None:
            continue
        if mode == "quote":
            exits = _exit_prices_from_quote(trade, await quote_client.get_quote(trade.symbol) or {})
            reason = "auto-settled 30 min before the close at the mids (quotes ~15 min delayed)"
        else:
            close = store.close_on(expiry, trade.symbol)
            if close is None:
                continue                                 # the official close hasn't arrived yet
            exits = [rules.intrinsic(leg.option_type, leg.strike, close) for leg in trade.legs]
            reason = f"settled at intrinsic against the {expiry} close ({close:,.2f}): the service missed 15:30"
        if exits is None:
            continue
        if store.close_trade(trade.id, exits, reason, now):
            closed += 1
            logger.info("paper trade %s settled: %s", trade.id, reason)
    return closed

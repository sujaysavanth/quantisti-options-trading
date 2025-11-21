"""Paper trading endpoints."""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..config import get_settings
from ..dependencies import get_market_stream_client, get_paper_store
from ..models.paper import PaperLegInput, PaperLegState, PaperTradeCreate, PaperTradeResponse
from ..services.market_stream_client import MarketStreamClient
from ..services.paper_store import PaperTradeStore, StoredLeg, StoredTrade

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/paper", tags=["paper-trading"])

settings = get_settings()
LOT_SIZE = settings.NIFTY_LOT_SIZE


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
    for key in ("last", "bid", "ask"):
        value = q_leg.get(key)
        if value not in (None, 0):
            return float(value)
    return 0.0


def build_response(trade: StoredTrade, quote: dict) -> PaperTradeResponse:
    leg_states: List[PaperLegState] = []
    entry_total = 0.0
    current_total = 0.0

    for leg in trade.legs:
        quote_leg = None
        if quote:
            quote_leg = _match_quote_leg(quote, leg)
        current_price = _price_from_quote(quote_leg) if quote_leg else None
        entry_price = leg.entry_price or 0.0
        side_mult = 1 if leg.side == "BUY" else -1
        entry_value = entry_price * leg.quantity * LOT_SIZE * side_mult
        current_value = (
            (current_price or 0.0) * leg.quantity * LOT_SIZE * side_mult
            if current_price is not None
            else entry_value
        )
        entry_total += entry_value
        current_total += current_value
        pnl = current_value - entry_value

        leg_states.append(
            PaperLegState(
                identifier=leg.identifier,
                strike=leg.strike,
                option_type=leg.option_type,  # type: ignore[arg-type]
                expiry=leg.expiry,  # type: ignore[arg-type]
                quantity=leg.quantity,
                side=leg.side,  # type: ignore[arg-type]
                entry_price=entry_price or None,
                current_price=current_price,
                pnl=pnl,
            )
        )

    return PaperTradeResponse(
        id=trade.id,
        symbol=trade.symbol,
        nickname=trade.nickname,
        created_at=trade.created_at,
        entry_notional=entry_total,
        current_notional=current_total,
        pnl=current_total - entry_total,
        legs=leg_states,
    )


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
        stored_legs.append(
            StoredLeg(
                identifier=leg.identifier or (quote_leg.get("identifier") if quote_leg else None),
                strike=leg.strike,
                option_type=leg.option_type,
                expiry=leg.expiry.isoformat(),
                quantity=leg.quantity,
                side=leg.side,
                entry_price=entry_price,
            )
        )

    trade = store.add_trade(payload.symbol, payload.nickname, stored_legs)
    return build_response(trade, quote)


@router.get("/orders", response_model=List[PaperTradeResponse], summary="List paper trades")
async def list_paper_orders(
    store: PaperTradeStore = Depends(get_paper_store),
    quote_client: MarketStreamClient = Depends(get_market_stream_client)
):
    trades = store.list_trades()
    responses: List[PaperTradeResponse] = []
    for trade in trades:
        quote = await quote_client.get_quote(trade.symbol) or {}
        responses.append(build_response(trade, quote))
    return responses


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


@router.delete("/orders/{trade_id}", status_code=204, summary="Delete paper trade")
async def delete_paper_order(
    trade_id: UUID,
    store: PaperTradeStore = Depends(get_paper_store)
):
    if not store.delete_trade(trade_id):
        raise HTTPException(status_code=404, detail="Trade not found")

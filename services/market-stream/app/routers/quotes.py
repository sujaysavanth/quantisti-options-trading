"""REST endpoints for quote ingestion and retrieval."""

from fastapi import APIRouter, Depends, HTTPException

from ..broadcaster import QuoteBroadcaster
from ..dependencies import get_broadcaster, get_quote_store
from ..schemas import QuoteSnapshot, QuoteUpsert
from ..storage import QuoteStore

router = APIRouter(prefix="/v1", tags=["quotes"])


@router.post("/quotes", response_model=QuoteSnapshot, summary="Upsert quote")
async def upsert_quote(
    payload: QuoteUpsert,
    store: QuoteStore = Depends(get_quote_store),
    broadcaster: QuoteBroadcaster = Depends(get_broadcaster)
):
    snapshot = await store.upsert(payload)
    await broadcaster.broadcast_quote(snapshot)
    return snapshot


@router.get("/quotes", response_model=list[QuoteSnapshot], summary="List quotes")
async def list_quotes(store: QuoteStore = Depends(get_quote_store)):
    return await store.list_all()


@router.get("/quotes/{symbol}", response_model=QuoteSnapshot, summary="Get quote by symbol")
async def get_quote(symbol: str, store: QuoteStore = Depends(get_quote_store)):
    snapshot = await store.get(symbol)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Quote for {symbol} not found")
    return snapshot

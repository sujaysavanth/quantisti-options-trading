"""WebSocket streaming endpoint."""

import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..broadcaster import QuoteBroadcaster
from ..dependencies import get_broadcaster, get_quote_store
from ..storage import QuoteStore

router = APIRouter(prefix="/ws", tags=["stream"])


@router.websocket("/quotes")
async def stream_quotes(
    websocket: WebSocket,
    broadcaster: QuoteBroadcaster = Depends(get_broadcaster),
    store: QuoteStore = Depends(get_quote_store)
):
    await broadcaster.register(websocket)
    snapshots = await store.list_all()
    if snapshots:
        await broadcaster.send_snapshot(websocket, snapshots)

    try:
        while True:
            # Keep the connection alive; clients don't need to send anything.
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        await broadcaster.unregister(websocket)
    except Exception:
        await broadcaster.unregister(websocket)
        raise

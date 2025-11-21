"""WebSocket connection manager for quote broadcasts."""

from __future__ import annotations

import asyncio
import json
from typing import Set

from fastapi import WebSocket

from .schemas import QuoteSnapshot


class QuoteBroadcaster:
    """Manages WebSocket subscribers."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def register(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def unregister(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast_quote(self, snapshot: QuoteSnapshot) -> None:
        """Send quote to all subscribers."""
        message = json.dumps({
            "type": "quote",
            "data": snapshot.model_dump(mode="json")
        })
        await self._broadcast_raw(message)

    async def send_snapshot(self, websocket: WebSocket, snapshots: list[QuoteSnapshot]) -> None:
        await websocket.send_text(json.dumps({
            "type": "snapshot",
            "data": [snap.model_dump(mode="json") for snap in snapshots]
        }))

    async def _broadcast_raw(self, message: str) -> None:
        async with self._lock:
            connections = list(self._connections)
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception:
                await self.unregister(connection)

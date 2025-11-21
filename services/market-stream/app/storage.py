"""In-memory quote store."""

from __future__ import annotations

import asyncio
from typing import Dict, List

from .schemas import QuoteSnapshot, QuoteUpsert


class QuoteStore:
    """Keeps the most recent quote per symbol."""

    def __init__(self) -> None:
        self._quotes: Dict[str, QuoteSnapshot] = {}
        self._lock = asyncio.Lock()

    async def upsert(self, payload: QuoteUpsert) -> QuoteSnapshot:
        """Insert/update quote."""
        snapshot = QuoteSnapshot(**payload.model_dump())
        async with self._lock:
            self._quotes[payload.symbol.upper()] = snapshot
        return snapshot

    async def get(self, symbol: str) -> QuoteSnapshot | None:
        async with self._lock:
            return self._quotes.get(symbol.upper())

    async def list_all(self) -> List[QuoteSnapshot]:
        async with self._lock:
            return list(self._quotes.values())

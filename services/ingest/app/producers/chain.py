"""Publishes the SPX option chain to options.chain.quotes: one message per expiry, keyed "SPX:<expiry>".

Keying by expiry keeps each expiry's snapshots in order within one partition,
while different expiries spread across partitions.

Free sources rate-limit. On HTTP 429 the poller skips polls for a while,
doubling the pause each time (90s, 180s, ... up to 15 min) until a fetch works.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from itertools import groupby
from typing import Optional

from ..sources.base import ChainSource
from .envelope import ChainPayload, QuotePayload, wrap
from .kafka import TOPIC_CHAIN, Publisher

log = logging.getLogger(__name__)

BACKOFF_START = timedelta(seconds=90)
BACKOFF_MAX = timedelta(minutes=15)


def is_rate_limited(exc: Exception) -> bool:
    response = getattr(exc, "response", None)          # httpx.HTTPStatusError
    if getattr(response, "status_code", None) == 429:
        return True
    return type(exc).__name__ == "YFRateLimitError"     # yfinance's own exception


class ChainPoller:
    def __init__(self, publisher: Publisher, source: ChainSource, expiries: int, moneyness: float):
        self._publisher = publisher
        self._source = source
        self._expiries = expiries
        self._moneyness = moneyness
        self.backoff: Optional[timedelta] = None
        self.paused_until: Optional[datetime] = None

    def poll_once(self, now: Optional[datetime] = None, force: bool = False) -> int:
        now = now or datetime.now(timezone.utc)
        if self.paused_until and now < self.paused_until and not force:
            log.info("chain: rate-limited, paused until %s", self.paused_until)
            return 0
        try:
            snap = self._source.fetch_chain(self._expiries, self._moneyness)
        except Exception as exc:
            if not is_rate_limited(exc):
                raise
            self.backoff = min(self.backoff * 2, BACKOFF_MAX) if self.backoff else BACKOFF_START
            self.paused_until = now + self.backoff
            log.warning("chain: %s returned 429, pausing %s", self._source.name, self.backoff)
            return 0
        self.backoff = self.paused_until = None

        sent = 0
        for expiry, quotes in groupby(snap.quotes, key=lambda q: q.expiry):   # quotes are sorted by expiry
            payload = ChainPayload(
                symbol=snap.symbol, expiry=expiry, session_date=snap.session_date, quoted_at=snap.quoted_at,
                underlying_price=snap.underlying_price,
                quotes=[QuotePayload(option_type=q.option_type, strike=q.strike, bid=q.bid, ask=q.ask, last=q.last,
                                     volume=q.volume, open_interest=q.open_interest,
                                     vendor_iv=q.vendor_iv, vendor_delta=q.vendor_delta) for q in quotes],
            )
            self._publisher.send(TOPIC_CHAIN, f"{snap.symbol}:{expiry}",
                                 wrap("chain.v1", snap.source, snap.delay_minutes, payload, now))
            sent += 1
        log.info("chain: %d expiries, %d contracts from %s (quoted %s)",
                 sent, len(snap.quotes), snap.source, snap.quoted_at)
        return sent

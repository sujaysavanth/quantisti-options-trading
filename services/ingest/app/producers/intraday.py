"""Publishes 1-minute SPX and VIX bars to market.bars.1m, one message per bar, keyed by symbol.

Each poll fetches recent bars and sends only the finished ones newer than the
last bar already sent for that symbol. The very first poll starts from the
open of the latest session, so a restart mid-day refills the day so far
(downstream upserts make the repeats harmless).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

from ..sources import yahoo
from .envelope import BarPayload, wrap
from .kafka import TOPIC_BARS, Publisher
from .schedule import latest_session, session_open

log = logging.getLogger(__name__)

SYMBOLS = ("SPX", "VIX")
INTERVAL = "1m"
# Conservative label: Yahoo doesn't state a delay per response, and index quotes can lag.
DELAY_MINUTES = 15


class IntradayPoller:
    def __init__(self, publisher: Publisher, fetch: Callable[..., List[yahoo.Bar]] = yahoo.fetch_bars):
        self._publisher = publisher
        self._fetch = fetch                       # injectable for tests
        self.last_sent: Dict[str, datetime] = {}

    def poll_once(self, now: Optional[datetime] = None) -> int:
        now = now or datetime.now(timezone.utc)
        sent = 0
        for symbol in SYMBOLS:
            since = self.last_sent.get(symbol) or session_open(latest_session(now))
            bars = self._fetch(symbol, INTERVAL, since, now)
            # The newest bar is usually still forming; only send bars whose minute has ended.
            done = [b for b in bars if b.ts + timedelta(minutes=1) <= now
                    and (symbol not in self.last_sent or b.ts > self.last_sent[symbol])]
            for b in done:
                payload = BarPayload(symbol=b.symbol, interval=b.interval, ts=b.ts, open=b.open,
                                     high=b.high, low=b.low, close=b.close, volume=b.volume)
                self._publisher.send(TOPIC_BARS, symbol, wrap("bars.v1", b.source, DELAY_MINUTES, payload, now))
            if done:
                self.last_sent[symbol] = done[-1].ts
            sent += len(done)
            log.info("intraday %s: %d new bars", symbol, len(done))
        return sent

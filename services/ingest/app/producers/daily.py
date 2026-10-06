"""Publishes daily rows to market.daily after the close, keyed "<dataset>:<symbol>".

Each run re-sends the last LOOKBACK_DAYS of every dataset, not just today:
FRED posts a rate a day or more late and CBOE's VIX file can lag too, so a
short lookback catches late rows. Downstream upserts make repeats harmless.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from .. import market_spec
from ..sources import cboe, fred, yahoo
from .envelope import DailyPayload, wrap
from .kafka import TOPIC_DAILY, Publisher

log = logging.getLogger(__name__)

LOOKBACK_DAYS = 7


class DailyPoller:
    def __init__(self, publisher: Publisher,
                 fetch_spx: Callable = yahoo.fetch_daily,
                 fetch_vix: Callable = cboe.fetch_vix_history,
                 fetch_rates: Callable = fred.fetch_rates):
        self._publisher = publisher
        self._fetch_spx, self._fetch_vix, self._fetch_rates = fetch_spx, fetch_vix, fetch_rates   # injectable for tests

    def _send(self, source: str, payload: DailyPayload, now: datetime) -> None:
        # End-of-day values are final, so no delay applies.
        self._publisher.send(TOPIC_DAILY, f"{payload.dataset}:{payload.symbol}", wrap("daily.v1", source, 0, payload, now))

    def poll_once(self, now: Optional[datetime] = None) -> int:
        now = now or datetime.now(timezone.utc)
        end = now.astimezone(market_spec.TZ).date()
        start = end - timedelta(days=LOOKBACK_DAYS)
        sent = 0

        for b in self._fetch_spx("SPX", start, end):
            if market_spec.is_trading_day(b.date) and now < market_spec.session_close(b.date):
                continue                       # today's bar is still moving
            self._send("yahoo", DailyPayload(dataset="underlying", symbol="SPX", date=b.date, open=b.open,
                                             high=b.high, low=b.low, close=b.close, volume=b.volume), now)
            sent += 1
        for row in self._fetch_vix(start=start, end=end):
            self._send("cboe", DailyPayload(dataset="vix", symbol="VIX", date=row.date, close=row.close), now)
            sent += 1
        for row in self._fetch_rates(start=start, end=end):
            self._send("fred", DailyPayload(dataset="rates", symbol="DGS3MO", date=row.date, rate=row.rate), now)
            sent += 1

        log.info("daily: %d rows for %s..%s", sent, start, end)
        return sent

"""Turns one backfill request into data messages on the normal topics.

Backfilled rows take the same path as live ones (market.daily / market.bars.1m / options.chain.quotes
-> Spark -> Postgres), so they get the same validation, dedupe and DLQ handling. The worker never
writes the data tables itself and never marks a gap filled: the next gap check does that once the
rows are actually stored.

Outcomes:
    published      n messages sent; the next check should see the data
    unrecoverable  the source can no longer supply this session (status set right away; not an error)
    failed         the source errored or returned nothing; the next scan asks again (up to MAX_ATTEMPTS)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Callable, Optional

from .. import market_spec
from ..gaps.expected import in_source_window
from ..producers.envelope import BackfillPayload, DailyPayload, wrap
from ..producers.kafka import TOPIC_DAILY, Publisher
from ..sources import cboe, fred, yahoo
from ..sources.indexes import BY_SYMBOL, fetch_index
from ..sources.session import session_for
from .intraday import Range, backfill_range

log = logging.getLogger(__name__)


@dataclass
class Outcome:
    kind: str           # published | unrecoverable | failed
    sent: int = 0
    detail: str = ""


class Worker:
    def __init__(self, publisher: Publisher,
                 fetch_spx: Callable = yahoo.fetch_daily,
                 fetch_vix: Callable = cboe.fetch_vix_history,
                 fetch_rates: Callable = fred.fetch_rates,
                 fetch_index: Callable = fetch_index,
                 fill_intraday: Callable = backfill_range,
                 poll_chain: Optional[Callable[[], int]] = None):
        self._publisher = publisher
        self._fetch_spx, self._fetch_vix, self._fetch_rates = fetch_spx, fetch_vix, fetch_rates
        self._fetch_index = fetch_index
        self._fill_intraday = fill_intraday
        self._poll_chain = poll_chain       # ChainPoller(...).poll_once(force=True); injected by the consumer

    def _daily(self, source: str, payload: DailyPayload, now: datetime) -> None:
        self._publisher.send(TOPIC_DAILY, f"{payload.dataset}:{payload.symbol}", wrap("daily.v1", source, 0, payload, now))

    def handle(self, req: BackfillPayload, now: Optional[datetime] = None) -> Outcome:
        now = now or datetime.now(timezone.utc)
        d = req.date
        try:
            if req.dataset == "daily":
                bars = self._fetch_spx("SPX", d, d)
                for b in bars:
                    self._daily("yahoo", DailyPayload(dataset="underlying", symbol="SPX", date=b.date, open=b.open,
                                                      high=b.high, low=b.low, close=b.close, volume=b.volume), now)
                return Outcome("published", len(bars)) if bars else Outcome("failed", detail=f"Yahoo has no SPX row for {d}")

            if req.dataset == "vix":
                rows = self._fetch_vix(start=d, end=d)
                for r in rows:
                    self._daily("cboe", DailyPayload(dataset="vix", symbol="VIX", date=r.date, close=r.close), now)
                return Outcome("published", len(rows)) if rows else Outcome("failed", detail=f"CBOE has no VIX close for {d}")

            if req.dataset == "rates":
                rows = self._fetch_rates(start=d, end=d)
                for r in rows:
                    self._daily("fred", DailyPayload(dataset="rates", symbol="DGS3MO", date=r.date, rate=r.rate), now)
                return Outcome("published", len(rows)) if rows else Outcome("failed", detail=f"FRED has no rate for {d}")

            if req.dataset == "index":
                series = BY_SYMBOL.get(req.symbol)
                if series is None:
                    return Outcome("failed", detail=f"unknown index {req.symbol!r}")
                rows = self._fetch_index(series, d, d)
                for r in rows:
                    self._daily(series.source, DailyPayload(dataset="index", symbol=r.symbol, date=r.date,
                                                            close=r.close), now)
                return (Outcome("published", len(rows)) if rows
                        else Outcome("failed", detail=f"{series.source.upper()} has no {req.symbol} value for {d}"))

            if req.dataset == "intraday":
                symbol, _, interval = req.symbol.partition(":")
                if not in_source_window(d, interval, now):
                    window = yahoo.LIMITS[interval][0].days
                    return Outcome("unrecoverable", detail=f"older than Yahoo's {window}-day {interval} window")
                # The whole ET calendar day: Yahoo labels VIX hourly bars on the hour, so the first one
                # starts at 09:00, before the open. to_bars keeps only bars that overlap the session.
                start = datetime.combine(d, time(0), market_spec.TZ).astimezone(timezone.utc)
                end = min(start + timedelta(days=1), now)
                res = self._fill_intraday(self._publisher, Range(symbol, interval, start, end))
                if res.error:
                    return Outcome("failed", detail=res.error)
                return Outcome("published", res.bars) if res.bars else Outcome("failed", detail=f"Yahoo returned no {interval} bars")

            if req.dataset == "chain":
                # Free sources only serve the chain as it is now, which belongs to session_for(now).
                if d < session_for(now) or self._poll_chain is None:
                    return Outcome("unrecoverable", detail="no free source for past option chains")
                sent = self._poll_chain()
                return Outcome("published", sent) if sent else Outcome("failed", detail="chain source returned nothing")
        except Exception as exc:
            return Outcome("failed", detail=f"{type(exc).__name__}: {exc}")
        return Outcome("failed", detail=f"unknown dataset {req.dataset!r}")

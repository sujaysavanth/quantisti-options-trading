"""Backfill historical intraday bars into market.bars.1m, the same topic the live poller uses.

Going through the live topic means history gets exactly the same treatment as live data:
Spark validates it, dedupes it, sends bad bars to the DLQ and upserts intraday_bars.
Each message carries its own `interval`, so 5m and 1h bars land as 5m and 1h rows.

Yahoo only serves recent intraday history (yahoo.LIMITS): 1m ~30 days, 5m 60 days,
1h ~730 days. `plan_ranges` asks for at most that; anything older is gone for good.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, List, Optional, Sequence

from ..producers.chain import is_rate_limited
from ..producers.envelope import BarPayload, wrap
from ..producers.kafka import TOPIC_BARS, Publisher
from ..sources import yahoo

log = logging.getLogger(__name__)

SYMBOLS = ("SPX", "VIX")
INTERVALS = ("1h", "5m", "1m")          # coarse first: the longest history lands first
RETRY_WAITS = (30, 60, 120)             # seconds to wait after a rate limit before each retry
PAUSE_SECONDS = 1.0                     # between Yahoo requests


@dataclass(frozen=True)
class Range:
    symbol: str
    interval: str
    start: datetime
    end: datetime


@dataclass
class RangeResult:
    range: Range
    bars: int = 0
    error: Optional[str] = None


def plan_ranges(now: datetime, intervals: Iterable[str] = INTERVALS, symbols: Iterable[str] = SYMBOLS,
                days: Optional[float] = None) -> List[Range]:
    """What to fetch: per symbol and interval, as far back as Yahoo allows (or `days`, if smaller)."""
    ranges = []
    for interval in intervals:
        window, _ = yahoo.LIMITS[interval]
        # fetch_bars refuses anything older than this (an hour of margin inside Yahoo's window).
        oldest = now - window + timedelta(hours=1)
        start = max(oldest, now - timedelta(days=days)) if days else oldest
        ranges += [Range(symbol, interval, start, now) for symbol in symbols]
    return ranges


def strict_download(pause: float = PAUSE_SECONDS, sleep: Callable[[float], None] = time.sleep):
    """A Yahoo download that raises on errors and pauses before each request.

    yf.download() swallows errors (a rate-limited request just returns no rows, which would look like
    "no data"), so this goes through Ticker.history with exceptions turned on.
    """
    import yfinance as yf
    yf.config.debug.hide_exceptions = False

    def download(tickers, start, end, interval):
        sleep(pause)
        return yf.Ticker(tickers).history(start=start, end=end, interval=interval,
                                          auto_adjust=False, actions=False)
    return download


def backfill_range(publisher: Publisher, rng: Range,
                   fetch: Callable[..., List[yahoo.Bar]] = yahoo.fetch_bars,
                   download: Optional[Callable] = None,
                   sleep: Callable[[float], None] = time.sleep,
                   retry_waits: Sequence[float] = RETRY_WAITS) -> RangeResult:
    """Fetch one range and publish its bars. Rate limits are retried; other errors are reported, not raised."""
    download = download or strict_download(sleep=sleep)
    result = RangeResult(rng)
    for attempt in range(len(retry_waits) + 1):
        try:
            bars = fetch(rng.symbol, rng.interval, rng.start, rng.end, download=download)
            break
        except Exception as exc:
            if is_rate_limited(exc) and attempt < len(retry_waits):
                log.warning("%s %s rate-limited; retrying in %ss", rng.symbol, rng.interval, retry_waits[attempt])
                sleep(retry_waits[attempt])
                continue
            result.error = f"{type(exc).__name__}: {exc}"
            return result

    now = datetime.now(timezone.utc)
    for b in bars:
        payload = BarPayload(symbol=b.symbol, interval=b.interval, ts=b.ts, open=b.open, high=b.high,
                             low=b.low, close=b.close, volume=b.volume)
        # History is final, so no delay applies.
        publisher.send(TOPIC_BARS, b.symbol, wrap("bars.v1", b.source, 0, payload, now))
    result.bars = len(bars)
    return result


def backfill(publisher: Publisher, ranges: Iterable[Range], **kwargs) -> List[RangeResult]:
    results = []
    for rng in ranges:
        res = backfill_range(publisher, rng, **kwargs)
        log.info("%s %s %s..%s: %s", rng.symbol, rng.interval, rng.start.date(), rng.end.date(),
                 res.error or f"{res.bars} bars")
        results.append(res)
    return results

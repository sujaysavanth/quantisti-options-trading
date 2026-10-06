"""Runs the three pollers on their schedules.

Every TICK seconds the loop checks the clock:
- market open:       intraday every INTRADAY_POLL_SECONDS, chain every CHAIN_POLL_SECONDS
- after the close:   once per session, final bars + closing chain + daily rows
A failing poll is logged and retried on its next turn; it never stops the loop.
The fetch libraries block, so the loop runs in its own thread next to the web app.
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Dict, Optional

from ..config import Settings
from ..sources import chain_source
from .chain import ChainPoller
from .daily import DailyPoller
from .intraday import IntradayPoller
from .kafka import Publisher
from .schedule import eod_due, is_market_open

log = logging.getLogger(__name__)

TICK_SECONDS = 5


class Runner:
    def __init__(self, settings: Settings, publisher: Publisher,
                 intraday: Optional[IntradayPoller] = None, chain: Optional[ChainPoller] = None,
                 daily: Optional[DailyPoller] = None):
        self.publisher = publisher
        self.intraday = intraday or IntradayPoller(publisher)
        self.chain = chain or ChainPoller(publisher, chain_source(settings.CHAIN_SOURCE),
                                          settings.CHAIN_EXPIRIES, settings.CHAIN_MONEYNESS)
        self.daily = daily or DailyPoller(publisher)
        self._every = {"intraday": timedelta(seconds=settings.INTRADAY_POLL_SECONDS),
                       "chain": timedelta(seconds=settings.CHAIN_POLL_SECONDS)}
        self._next: Dict[str, datetime] = {}
        self.eod_done: Optional[date] = None
        self.status: Dict[str, dict] = {}       # shown at GET /v1/producers

    def _run(self, name: str, poll: Callable[[], int], now: datetime) -> None:
        try:
            sent = poll()
            self.status[name] = {"last_run": now, "sent": sent, "error": None}
        except Exception as exc:
            log.exception("%s poll failed", name)
            self.status[name] = {"last_run": now, "sent": 0, "error": str(exc)}

    def tick(self, now: Optional[datetime] = None) -> None:
        now = now or datetime.now(timezone.utc)
        if is_market_open(now):
            if now >= self._next.get("intraday", now):
                self._run("intraday", lambda: self.intraday.poll_once(now), now)
                self._next["intraday"] = now + self._every["intraday"]
            if now >= self._next.get("chain", now):
                self._run("chain", lambda: self.chain.poll_once(now), now)
                self._next["chain"] = now + self._every["chain"]

        session = eod_due(now, self.eod_done)
        if session:
            log.info("end-of-day run for %s", session)
            self._run("intraday", lambda: self.intraday.poll_once(now), now)
            self._run("chain", lambda: self.chain.poll_once(now, force=True), now)
            self._run("daily", lambda: self.daily.poll_once(now), now)
            self.eod_done = session
        self.publisher.flush(10)

    def run_forever(self, stop: threading.Event) -> None:
        log.info("producers started")
        while not stop.is_set():
            try:
                self.tick()
            except Exception:
                log.exception("runner tick failed")
            stop.wait(TICK_SECONDS)
        self.publisher.flush(10)
        log.info("producers stopped")

"""Runs the gap scan every GAP_SCAN_MINUTES and the cheap re-check every GAP_RECHECK_SECONDS.

The first scan runs FIRST_SCAN_AFTER after startup, so a restart doesn't hit Postgres and the
sources before the rest of the stack is up. POST /v1/gaps/scan runs one right away; a lock keeps
a manual scan and a scheduled one from overlapping.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..db import connect
from ..producers.kafka import Publisher
from .scan import ScanResult, recheck, scan

log = logging.getLogger(__name__)

FIRST_SCAN_AFTER = timedelta(minutes=1)
TICK_SECONDS = 5


class GapScheduler:
    def __init__(self, database_url: str, publisher: Publisher, scan_every: timedelta, recheck_every: timedelta):
        self.database_url, self.publisher = database_url, publisher
        self.scan_every, self.recheck_every = scan_every, recheck_every
        self.lock = threading.Lock()
        self.last_scan: Optional[ScanResult] = None
        self.last_error: Optional[str] = None
        self.next_scan: Optional[datetime] = None
        self.next_recheck: Optional[datetime] = None

    def scan_now(self) -> ScanResult:
        with self.lock, connect(self.database_url) as conn:
            self.last_scan = scan(conn, self.publisher)
        self.last_error = None
        self.next_scan = self.last_scan.at + self.scan_every
        return self.last_scan

    def recheck_now(self) -> int:
        with self.lock, connect(self.database_url) as conn:
            return recheck(conn)

    def tick(self, now: datetime) -> None:
        try:
            if now >= self.next_scan:
                self.scan_now()
                self.next_recheck = now + self.recheck_every
            elif now >= self.next_recheck:
                self.recheck_now()
                self.next_recheck = now + self.recheck_every
        except Exception as exc:
            log.exception("gap scan failed")
            self.last_error = str(exc)
            self.next_scan = self.next_recheck = now + self.recheck_every   # try again soon, not in an hour

    def run_forever(self, stop: threading.Event) -> None:
        start = datetime.now(timezone.utc)
        self.next_scan = start + FIRST_SCAN_AFTER
        self.next_recheck = start + self.recheck_every
        log.info("gap scheduler started: first scan at %s", self.next_scan)
        while not stop.is_set():
            self.tick(datetime.now(timezone.utc))
            stop.wait(TICK_SECONDS)

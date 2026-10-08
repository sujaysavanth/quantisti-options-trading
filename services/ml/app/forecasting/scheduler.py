"""The weekly refresh, on its own: a background thread that forecasts each new week after its close.

Every CHECK_SECONDS it asks: is the newest SPX daily row the last session of its week, has GRACE passed since
that session's close, and is there no forecast for it yet? Only then does it run serving.refresh(). The daily
row arrives ~16:20 ET (the ingest end-of-day run), so the forecast is usually stored by ~16:50 ET on Friday.
Anything that fails is logged and retried on the next check.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from .. import market_spec
from ..dataset.weeks import anchor_of_week

log = logging.getLogger(__name__)

CHECK_SECONDS = 300
GRACE = timedelta(minutes=45)


def due(latest_session, have_forecast: bool, now: datetime) -> bool:
    """A complete week (its last session closed GRACE ago) with no forecast yet."""
    if latest_session is None or have_forecast or anchor_of_week(latest_session) != latest_session:
        return False
    return now >= market_spec.session_close(latest_session) + GRACE


class ForecastScheduler:
    def __init__(self, connection):
        self.connection = connection          # context manager yielding a DB connection
        self.last_run: Optional[dict] = None
        self.last_error: Optional[str] = None

    def check(self, now: Optional[datetime] = None) -> bool:
        from ..dataset import store
        from . import serving
        now = now or datetime.now(timezone.utc)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT max(date) FROM underlying_daily WHERE symbol = 'SPX'")
                latest = cur.fetchone()[0]
            if not due(latest, latest in store.forecast_anchors(conn), now):
                return False
            self.last_run = {"at": now.isoformat(timespec="seconds"), **serving.refresh(conn)}
        log.info("weekly forecast refresh: %s", self.last_run)
        return True

    def run_forever(self, stop: threading.Event) -> None:
        log.info("forecast scheduler started (checks every %ss)", CHECK_SECONDS)
        while not stop.is_set():
            try:
                self.check()
                self.last_error = None
            except Exception as exc:
                log.exception("forecast refresh failed")
                self.last_error = str(exc)
            stop.wait(CHECK_SECONDS)

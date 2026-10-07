"""Ingest service.

Fetches SPX/VIX market data, option chains and rates from free sources (see
app/sources/) and publishes them to Kafka (see app/producers/). Background threads:
- producers:  the polling loop
- gaps:       the gap scan (hourly) and re-check (every 2 min), see app/gaps/
- backfill:   the worker that turns backfill requests into data messages, see app/backfill/
This web app exposes health checks, the pollers' status, and the gap list and scan trigger.
"""

import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Response

from . import db
from .backfill.consumer import BackfillConsumer
from .backfill.worker import Worker
from .config import get_settings
from .gaps import store
from .gaps.detector import Coverage, known_ranges
from .gaps.scheduler import GapScheduler
from .producers.kafka import Publisher
from .producers.runner import Runner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()
publisher = Publisher(settings.KAFKA_BOOTSTRAP)
runner = Runner(settings, publisher)
gaps = GapScheduler(settings.DATABASE_URL, publisher, timedelta(minutes=settings.GAP_SCAN_MINUTES),
                    timedelta(seconds=settings.GAP_RECHECK_SECONDS))
backfill = BackfillConsumer(settings.KAFKA_BOOTSTRAP, settings.DATABASE_URL, publisher,
                            Worker(publisher, poll_chain=lambda: runner.chain.poll_once(force=True)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = threading.Event()
    threads = []
    if settings.PRODUCERS_ENABLED:
        threads.append(threading.Thread(target=runner.run_forever, args=(stop,), name="producers", daemon=True))
    if settings.GAPS_ENABLED:
        threads.append(threading.Thread(target=gaps.run_forever, args=(stop,), name="gaps", daemon=True))
        threads.append(threading.Thread(target=backfill.run, args=(stop,), name="backfill", daemon=True))
    for t in threads:
        t.start()
    yield
    stop.set()
    for t in threads:
        t.join(timeout=15)


app = FastAPI(title=settings.SERVICE_NAME, version="0.3.0", lifespan=lifespan)


@app.get("/health/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    """The process is up."""
    return {"status": "ok"}


@app.get("/health/readyz", tags=["health"])
def readyz(response: Response) -> dict:
    """Ready when the Kafka broker answers. Postgres is reported but optional: only gap scans need it."""
    error = publisher.ping()
    if error:
        response.status_code = 503
    return {"status": "not ready" if error else "ready", "kafka": settings.KAFKA_BOOTSTRAP,
            "kafka_error": error, "chain_source": settings.CHAIN_SOURCE,
            "database_error": db.ping(settings.DATABASE_URL) if settings.GAPS_ENABLED else None}


@app.get("/v1/producers", tags=["producers"])
async def producers() -> dict:
    """Last run of each poller, messages delivered/failed per topic, and any rate-limit pause."""
    return {
        "enabled": settings.PRODUCERS_ENABLED,
        "pollers": runner.status,
        "eod_done": runner.eod_done,
        "chain_paused_until": runner.chain.paused_until,
        "delivered": dict(publisher.delivered),
        "failed": dict(publisher.failed),
    }


@app.post("/v1/gaps/scan", tags=["gaps"])
def scan_gaps() -> dict:
    """Run a gap scan now: re-check open gaps, find new ones, request backfills."""
    try:
        return vars(gaps.scan_now())
    except Exception as exc:
        raise HTTPException(503, f"gap scan failed: {exc}")


@app.get("/v1/gaps", tags=["gaps"])
def list_gaps(status: Optional[Literal["requested", "filled", "unrecoverable"]] = None,
              dataset: Optional[Literal["daily", "vix", "rates", "intraday", "chain"]] = None,
              limit: int = 500) -> dict:
    """Gaps (newest first), counts per dataset and status, known ranges, and the last scan / worker result."""
    try:
        with db.connect(settings.DATABASE_URL) as conn:
            rows = store.list_gaps(conn, status, dataset, limit)
            counts = store.count_gaps(conn)
            today = datetime.now(timezone.utc).date()
            known = known_ranges(Coverage(collection_start=store.collection_start(conn)), today)
    except Exception as exc:
        raise HTTPException(503, f"database unavailable: {exc}")
    return {
        "counts": counts,
        "known": [vars(k) for k in known],
        "gaps": rows,
        "last_scan": vars(gaps.last_scan) if gaps.last_scan else None,
        "next_scan": gaps.next_scan,
        "scan_error": gaps.last_error,
        "worker": {"handled": backfill.handled, "last": backfill.last},
    }


@app.get("/", tags=["root"])
async def root() -> dict:
    return {"service": settings.SERVICE_NAME, "docs": "/docs", "health": "/health/healthz",
            "producers": "/v1/producers", "gaps": "/v1/gaps"}

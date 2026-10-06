"""Ingest service.

Fetches SPX/VIX market data, option chains and rates from free sources (see
app/sources/) and publishes them to Kafka (see app/producers/). The polling
loop runs in a background thread; this web app exposes health checks and the
pollers' status. Later modules add triggers such as a gap scan.
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from .config import get_settings
from .producers.kafka import Publisher
from .producers.runner import Runner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()
publisher = Publisher(settings.KAFKA_BOOTSTRAP)
runner = Runner(settings, publisher)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = threading.Event()
    thread = None
    if settings.PRODUCERS_ENABLED:
        thread = threading.Thread(target=runner.run_forever, args=(stop,), name="producers", daemon=True)
        thread.start()
    yield
    stop.set()
    if thread:
        thread.join(timeout=15)


app = FastAPI(title=settings.SERVICE_NAME, version="0.2.0", lifespan=lifespan)


@app.get("/health/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    """The process is up."""
    return {"status": "ok"}


@app.get("/health/readyz", tags=["health"])
def readyz(response: Response) -> dict:
    """Ready when the Kafka broker answers."""
    error = publisher.ping()
    if error:
        response.status_code = 503
    return {"status": "not ready" if error else "ready", "kafka": settings.KAFKA_BOOTSTRAP,
            "kafka_error": error, "chain_source": settings.CHAIN_SOURCE}


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


@app.get("/", tags=["root"])
async def root() -> dict:
    return {"service": settings.SERVICE_NAME, "docs": "/docs", "health": "/health/healthz", "producers": "/v1/producers"}

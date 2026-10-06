"""Ingest service.

Fetches SPX/VIX market data, option chains and rates from free sources (see
app/sources/) and, from Module 4 on, publishes them to Kafka. This web app only
exposes health checks for now; later modules add triggers such as a gap scan.
"""

from fastapi import FastAPI

from .config import get_settings

settings = get_settings()
app = FastAPI(title=settings.SERVICE_NAME, version="0.1.0")


@app.get("/health/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    """The process is up."""
    return {"status": "ok"}


@app.get("/health/readyz", tags=["health"])
async def readyz() -> dict[str, str]:
    """Ready to work. Will also check the Kafka connection once producers exist (Module 4)."""
    return {"status": "ready", "chain_source": settings.CHAIN_SOURCE, "kafka": settings.KAFKA_BOOTSTRAP}


@app.get("/", tags=["root"])
async def root() -> dict:
    return {"service": settings.SERVICE_NAME, "docs": "/docs", "health": "/health/healthz"}

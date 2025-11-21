"""Entry point for market stream service."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .broadcaster import QuoteBroadcaster
from .config import get_settings
from .routers import health, quotes, stream
from .storage import QuoteStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.SERVICE_NAME,
    version=settings.VERSION,
    description="Realtime quote distribution service"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# shared state
app.state.quote_store = QuoteStore()
app.state.quote_broadcaster = QuoteBroadcaster()

# routers
app.include_router(health.router, prefix="/health")
app.include_router(quotes.router)
app.include_router(stream.router)


@app.get("/")
async def root():
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "status": "running"
    }

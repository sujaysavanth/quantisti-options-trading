"""Portfolio service.

Purpose:
    - Open positions netted across the simulator's paper trades
    - Snapshots of the paper account (every 15 min in session, once after each close) for the equity curve
    - Trade history and CSV export
The simulator owns the trades; this service reads them over HTTP and owns only portfolio_snapshots (schema 013).
"""

import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .clients import MarketStreamClient, SimulatorClient
from .config import get_settings
from .db.connection import close_db_connection, initialize_pool
from .routers import health, portfolio
from .services.snapshots import SnapshotStore, take_due

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(title=settings.SERVICE_NAME, version=settings.VERSION,
              description="Paper portfolio: positions, snapshots, trade history", docs_url="/docs")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(health.router, prefix="/health")
app.include_router(portfolio.router)


@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.SERVICE_NAME} v{settings.VERSION}")
    try:
        initialize_pool(min_conn=1, max_conn=5)
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    app.state.snapshot_store = SnapshotStore()
    if settings.SNAPSHOTS_ENABLED:
        app.state.snapshotter = asyncio.create_task(_snapshot_forever(app.state.snapshot_store))


async def _snapshot_forever(store: SnapshotStore) -> None:
    """Every minute: take the intraday or close snapshot that is due, if it isn't stored yet."""
    simulator, stream = SimulatorClient(), MarketStreamClient()
    while True:
        try:
            await take_due(store, simulator, stream)
        except Exception:
            logger.exception("portfolio snapshot failed")
        await asyncio.sleep(settings.SNAPSHOT_CHECK_SECONDS)


@app.on_event("shutdown")
async def shutdown_event():
    task = getattr(app.state, "snapshotter", None)
    if task:
        task.cancel()
    close_db_connection()


@app.get("/", tags=["root"])
async def root():
    return {"service": settings.SERVICE_NAME, "version": settings.VERSION, "status": "running",
            "endpoints": {"docs": "/docs", "health": "/health/healthz", "positions": "/v1/portfolio/positions",
                          "equity": "/v1/portfolio/equity", "trades": "/v1/portfolio/trades"}}

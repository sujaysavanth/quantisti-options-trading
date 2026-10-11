"""Stats & risk service.

Purpose:
    - Risk of the open paper portfolio: Greeks, stress scenarios, 1-day VaR / expected shortfall (three methods)
    - VaR stored once per session after the close (schema 014 risk_var) and backtested against the realised P&L
Positions come from the portfolio service, trades / account / capital rules from the simulator, prices from
market-stream, the GARCH volatility from ml, rates and SPX / VIX history from Postgres.
"""

import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db.connection import close_db_connection, initialize_pool
from .routers import health, risk
from .services.var_run import VarStore, store_due

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(title=settings.SERVICE_NAME, version=settings.VERSION,
              description="Risk of the paper portfolio: Greeks, stress, VaR", docs_url="/docs")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(health.router, prefix="/health")
app.include_router(risk.router)


@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.SERVICE_NAME} v{settings.VERSION}")
    try:
        initialize_pool(min_conn=1, max_conn=5)
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    app.state.var_store = VarStore()
    if settings.VAR_STORE_ENABLED:
        app.state.var_task = asyncio.create_task(_store_var_forever(app.state.var_store))


async def _store_var_forever(store: VarStore) -> None:
    """Every minute: store the session's VaR once it is due (20 min after the close until 20:15 ET)."""
    while True:
        try:
            await store_due(store)
        except Exception:
            logger.exception("VaR store failed")
        await asyncio.sleep(settings.VAR_CHECK_SECONDS)


@app.on_event("shutdown")
async def shutdown_event():
    task = getattr(app.state, "var_task", None)
    if task:
        task.cancel()
    close_db_connection()


@app.get("/", tags=["root"])
async def root():
    return {"service": settings.SERVICE_NAME, "version": settings.VERSION, "status": "running",
            "endpoints": {"docs": "/docs", "health": "/health/healthz", "greeks": "/v1/risk/greeks",
                          "stress": "/v1/risk/stress", "var": "/v1/risk/var", "var_history": "/v1/risk/var/history"}}

"""Stats & risk service.

Purpose:
    - Risk of the open paper portfolio: Greeks now; stress scenarios and VaR/CVaR next
Positions come from the portfolio service, prices from market-stream, the rate from rates_daily.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db.connection import close_db_connection, initialize_pool
from .routers import health, risk

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


@app.on_event("shutdown")
async def shutdown_event():
    close_db_connection()


@app.get("/", tags=["root"])
async def root():
    return {"service": settings.SERVICE_NAME, "version": settings.VERSION, "status": "running",
            "endpoints": {"docs": "/docs", "health": "/health/healthz", "greeks": "/v1/risk/greeks"}}

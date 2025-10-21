"""Market data service.

Purpose:
    - Provides market and options reference data for Nifty options
    - Generates option chains with Black-Scholes pricing
    - Calculates Greeks for options
    - Serves historical Nifty OHLCV data

Features:
    - Black-Scholes pricing for European options
    - Greeks calculation (Delta, Gamma, Theta, Vega, Rho)
    - Historical volatility-based pricing
    - Mock data generation for development/testing
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db.connection import initialize_pool, close_db_connection
from .routers import health, nifty, options

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.SERVICE_NAME,
    version=settings.VERSION,
    description="Market data service providing Nifty options data with Black-Scholes pricing",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/health")
app.include_router(nifty.router, prefix="/v1")
app.include_router(options.router, prefix="/v1")


@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup."""
    logger.info(f"Starting {settings.SERVICE_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENV}")

    try:
        # Initialize database connection pool
        initialize_pool(min_conn=2, max_conn=10)
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Don't crash the service - allow it to start and report errors via health check


@app.on_event("shutdown")
async def shutdown_event():
    """Close connections on shutdown."""
    logger.info("Shutting down Market Service")
    try:
        close_db_connection()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with service information."""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "health": "/health/healthz",
            "nifty_spot": "/v1/nifty/spot",
            "nifty_historical": "/v1/nifty/historical",
            "option_chain": "/v1/options/chain"
        }
    }

"""Machine learning and feature engineering service.

Purpose:
    - Compute and store features for ML models
    - Host predictive models for strategy recommendations
    - Provide feature engineering pipeline

Endpoints:
    - /v1/features/* - Feature computation and retrieval
    - /v1/predict - Model predictions (TODO)
    - /v1/model/* - Model management (TODO)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .routers import health, features
from .db.connection import initialize_pool, close_db_connection
from .config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    settings = get_settings()
    logger.info(f"Starting {settings.SERVICE_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENV}")

    # Initialize database connection pool
    try:
        initialize_pool(min_conn=2, max_conn=10)
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {e}")

    yield

    # Shutdown
    logger.info("Shutting down ML Features service")
    close_db_connection()


app = FastAPI(
    title="ML Features Service",
    version="0.1.0",
    lifespan=lifespan
)

# Include routers
app.include_router(health.router, prefix="/health")
app.include_router(features.router, prefix="/v1")

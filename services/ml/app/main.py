"""Machine learning service: the SPX weekly range forecast.

Purpose:
    - Build point-in-time weekly features and next-week labels (app/dataset/)
    - Forecast next week's closing range, store each forecast, and monitor calibration (app/forecasting/)

Endpoints:
    - /v1/features/* - weekly features: build all weeks (backfill), read one or the latest
    - /v1/predict/*  - the weekly forecast (served + second opinion + reference), monitoring, refresh

A background thread forecasts each new week after its Friday close (FORECAST_SCHEDULER_ENABLED).
CLI: python -m app.cli (see app/cli.py).
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .db.connection import close_db_connection, initialize_pool
from .routers import features, health, predict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"Starting {settings.SERVICE_NAME} v{settings.VERSION} ({settings.ENV})")
    try:
        initialize_pool(min_conn=2, max_conn=10)
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {e}")

    stop, thread = threading.Event(), None
    if settings.FORECAST_SCHEDULER_ENABLED:
        from .forecasting.scheduler import ForecastScheduler
        from .services.feature_service import _connection
        predict.SCHEDULER = ForecastScheduler(_connection)
        thread = threading.Thread(target=predict.SCHEDULER.run_forever, args=(stop,), name="forecasts", daemon=True)
        thread.start()
    yield
    stop.set()
    if thread:
        thread.join(timeout=10)
    close_db_connection()


app = FastAPI(title="ML Service", version="0.2.0", lifespan=lifespan)
app.include_router(health.router, prefix="/health")
app.include_router(features.router, prefix="/v1")
app.include_router(predict.router, prefix="/v1")

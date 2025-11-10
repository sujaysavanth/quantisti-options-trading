"""Backtest management and execution endpoints."""

import logging
from typing import List, Optional
from uuid import UUID
import asyncio

from fastapi import APIRouter, HTTPException, BackgroundTasks
from psycopg2.extras import RealDictCursor

from ..db.connection import get_db_connection, return_db_connection
from ..models.backtest import (
    BacktestCreate,
    BacktestResponse,
    BacktestListResponse,
    BacktestResultsResponse,
    Trade,
    TradeLeg,
    BacktestStatus
)
from ..models.metrics import PerformanceMetrics, MetricsResponse
from ..services.backtest_engine import BacktestEngine
from ..services.metrics_calculator import MetricsCalculator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtests", tags=["backtests"])

# Global instances
backtest_engine = BacktestEngine()
metrics_calculator = MetricsCalculator()


@router.post("/", response_model=BacktestResponse, summary="Create a new backtest")
async def create_backtest(backtest: BacktestCreate):
    """Create a new backtest configuration.

    Args:
        backtest: Backtest configuration

    Returns:
        Created backtest with database ID
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Verify strategy exists
        cursor.execute(
            "SELECT id FROM strategies WHERE id = %s",
            (backtest.strategy_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Strategy not found")

        # Insert backtest
        cursor.execute(
            """
            INSERT INTO backtests
            (strategy_id, name, start_date, end_date, initial_capital,
             entry_logic, exit_logic, stop_loss_pct, target_pct, max_holding_days, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING')
            RETURNING *
            """,
            (
                backtest.strategy_id, backtest.name, backtest.start_date, backtest.end_date,
                backtest.initial_capital, backtest.entry_logic.value, backtest.exit_logic.value,
                backtest.stop_loss_pct, backtest.target_pct, backtest.max_holding_days
            )
        )
        created_backtest = cursor.fetchone()

        conn.commit()
        cursor.close()

        return BacktestResponse(**dict(created_backtest))

    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error creating backtest: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        if conn:
            return_db_connection(conn)


@router.post("/{backtest_id}/run", response_model=BacktestResponse, summary="Run a backtest")
async def run_backtest(backtest_id: UUID, background_tasks: BackgroundTasks):
    """Execute a backtest in the background.

    Args:
        backtest_id: Backtest UUID
        background_tasks: FastAPI background tasks

    Returns:
        Backtest with RUNNING status
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Verify backtest exists and is in PENDING state
        cursor.execute(
            "SELECT * FROM backtests WHERE id = %s",
            (backtest_id,)
        )
        backtest = cursor.fetchone()

        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")

        if backtest['status'] != BacktestStatus.PENDING.value:
            raise HTTPException(
                status_code=400,
                detail=f"Backtest is in {backtest['status']} state, cannot run"
            )

        cursor.close()
        return_db_connection(conn)
        conn = None

        # Run backtest in background
        background_tasks.add_task(run_backtest_task, backtest_id)

        # Return immediately with PENDING status
        return BacktestResponse(**dict(backtest))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting backtest {backtest_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        if conn:
            return_db_connection(conn)


async def run_backtest_task(backtest_id: UUID):
    """Background task to run backtest."""
    try:
        logger.info(f"Starting backtest {backtest_id}")
        await backtest_engine.run_backtest(backtest_id)

        # Calculate metrics after completion
        logger.info(f"Calculating metrics for backtest {backtest_id}")
        metrics_calculator.calculate_metrics(backtest_id)

        logger.info(f"Backtest {backtest_id} completed successfully")

    except Exception as e:
        logger.error(f"Error in backtest task {backtest_id}: {e}")


@router.get("/", response_model=BacktestListResponse, summary="List all backtests")
async def list_backtests(
    strategy_id: Optional[UUID] = None,
    status: Optional[BacktestStatus] = None
):
    """Get list of all backtests.

    Args:
        strategy_id: Filter by strategy
        status: Filter by status

    Returns:
        List of backtests
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Build query
        query = "SELECT * FROM backtests WHERE 1=1"
        params = []

        if strategy_id:
            query += " AND strategy_id = %s"
            params.append(strategy_id)

        if status:
            query += " AND status = %s"
            params.append(status.value)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        backtests = cursor.fetchall()
        cursor.close()

        return BacktestListResponse(
            backtests=[BacktestResponse(**dict(b)) for b in backtests],
            count=len(backtests)
        )

    except Exception as e:
        logger.error(f"Error listing backtests: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        if conn:
            return_db_connection(conn)


@router.get("/{backtest_id}", response_model=BacktestResponse, summary="Get backtest by ID")
async def get_backtest(backtest_id: UUID):
    """Get a specific backtest.

    Args:
        backtest_id: Backtest UUID

    Returns:
        Backtest details
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            "SELECT * FROM backtests WHERE id = %s",
            (backtest_id,)
        )
        backtest = cursor.fetchone()

        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")

        cursor.close()

        return BacktestResponse(**dict(backtest))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting backtest {backtest_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        if conn:
            return_db_connection(conn)


@router.get("/{backtest_id}/trades", response_model=BacktestResultsResponse, summary="Get backtest trades")
async def get_backtest_trades(backtest_id: UUID):
    """Get all trades for a backtest.

    Args:
        backtest_id: Backtest UUID

    Returns:
        Backtest with all trades and legs
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get backtest
        cursor.execute(
            "SELECT * FROM backtests WHERE id = %s",
            (backtest_id,)
        )
        backtest = cursor.fetchone()

        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")

        # Get trades
        cursor.execute(
            """
            SELECT * FROM backtest_trades
            WHERE backtest_id = %s
            ORDER BY entry_date, trade_number
            """,
            (backtest_id,)
        )
        trades = cursor.fetchall()

        # Get legs for each trade
        result_trades = []
        for trade in trades:
            cursor.execute(
                "SELECT * FROM backtest_trade_legs WHERE trade_id = %s",
                (trade['id'],)
            )
            legs = cursor.fetchall()

            trade_dict = dict(trade)
            trade_dict['legs'] = [TradeLeg(**dict(leg)) for leg in legs]
            result_trades.append(Trade(**trade_dict))

        cursor.close()

        return BacktestResultsResponse(
            backtest=BacktestResponse(**dict(backtest)),
            trades=result_trades,
            trade_count=len(result_trades)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trades for backtest {backtest_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        if conn:
            return_db_connection(conn)


@router.get("/{backtest_id}/metrics", response_model=MetricsResponse, summary="Get backtest metrics")
async def get_backtest_metrics(backtest_id: UUID):
    """Get performance metrics for a backtest.

    Args:
        backtest_id: Backtest UUID

    Returns:
        Performance metrics
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get metrics
        cursor.execute(
            "SELECT * FROM backtest_metrics WHERE backtest_id = %s",
            (backtest_id,)
        )
        metrics = cursor.fetchone()

        if not metrics:
            raise HTTPException(
                status_code=404,
                detail="Metrics not found. Backtest may not be completed yet."
            )

        cursor.close()

        metrics_dict = dict(metrics)
        metrics_dict.pop('id', None)  # Remove metrics table ID

        return MetricsResponse(
            id=backtest_id,
            metrics=PerformanceMetrics(**metrics_dict)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metrics for backtest {backtest_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        if conn:
            return_db_connection(conn)

"""Strategy management endpoints."""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from psycopg2.extras import RealDictCursor

from ..db.connection import get_db_connection, return_db_connection
from ..models.strategy import (
    StrategyCreate,
    StrategyResponse,
    StrategyListResponse,
    StrategyLegResponse,
    StrategyType
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("/", response_model=StrategyListResponse, summary="List all strategies")
async def list_strategies(
    strategy_type: Optional[StrategyType] = None
):
    """Get list of all available strategies.

    Args:
        strategy_type: Filter by strategy type

    Returns:
        List of strategies with their legs
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Build query
        if strategy_type:
            query = "SELECT * FROM strategies WHERE strategy_type = %s ORDER BY name"
            cursor.execute(query, (strategy_type.value,))
        else:
            query = "SELECT * FROM strategies ORDER BY name"
            cursor.execute(query)

        strategies = cursor.fetchall()

        # Get legs for each strategy
        result_strategies = []
        for strategy in strategies:
            cursor.execute(
                "SELECT * FROM strategy_legs WHERE strategy_id = %s ORDER BY leg_order",
                (strategy['id'],)
            )
            legs = cursor.fetchall()

            strategy_dict = dict(strategy)
            strategy_dict['legs'] = [StrategyLegResponse(**dict(leg)) for leg in legs]
            result_strategies.append(StrategyResponse(**strategy_dict))

        cursor.close()

        return StrategyListResponse(
            strategies=result_strategies,
            count=len(result_strategies)
        )

    except Exception as e:
        logger.error(f"Error listing strategies: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        if conn:
            return_db_connection(conn)


@router.get("/{strategy_id}", response_model=StrategyResponse, summary="Get strategy by ID")
async def get_strategy(strategy_id: UUID):
    """Get a specific strategy with its legs.

    Args:
        strategy_id: Strategy UUID

    Returns:
        Strategy details with legs
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get strategy
        cursor.execute(
            "SELECT * FROM strategies WHERE id = %s",
            (strategy_id,)
        )
        strategy = cursor.fetchone()

        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

        # Get legs
        cursor.execute(
            "SELECT * FROM strategy_legs WHERE strategy_id = %s ORDER BY leg_order",
            (strategy_id,)
        )
        legs = cursor.fetchall()

        cursor.close()

        strategy_dict = dict(strategy)
        strategy_dict['legs'] = [StrategyLegResponse(**dict(leg)) for leg in legs]

        return StrategyResponse(**strategy_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategy {strategy_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        if conn:
            return_db_connection(conn)


@router.post("/", response_model=StrategyResponse, summary="Create custom strategy")
async def create_strategy(strategy: StrategyCreate):
    """Create a new custom strategy.

    Args:
        strategy: Strategy definition with legs

    Returns:
        Created strategy with database ID
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Insert strategy
        cursor.execute(
            """
            INSERT INTO strategies (name, strategy_type, description)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (strategy.name, strategy.strategy_type.value, strategy.description)
        )
        created_strategy = cursor.fetchone()
        strategy_id = created_strategy['id']

        # Insert legs
        created_legs = []
        for leg in strategy.legs:
            cursor.execute(
                """
                INSERT INTO strategy_legs
                (strategy_id, action, option_type, strike_offset, quantity, leg_order)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (strategy_id, leg.action.value, leg.option_type.value,
                 leg.strike_offset, leg.quantity, leg.leg_order)
            )
            created_legs.append(cursor.fetchone())

        conn.commit()
        cursor.close()

        strategy_dict = dict(created_strategy)
        strategy_dict['legs'] = [StrategyLegResponse(**dict(leg)) for leg in created_legs]

        return StrategyResponse(**strategy_dict)

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error creating strategy: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        if conn:
            return_db_connection(conn)

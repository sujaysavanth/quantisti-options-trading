"""PostgreSQL database connection management."""

import logging
from typing import Optional

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, register_uuid

from ..config import get_settings

logger = logging.getLogger(__name__)

# Global connection pool
_connection_pool: Optional[pool.SimpleConnectionPool] = None


def get_db_connection():
    """Get a database connection from the pool.

    Returns:
        psycopg2 connection with RealDictCursor

    Raises:
        RuntimeError: If connection pool is not initialized
    """
    global _connection_pool

    if _connection_pool is None:
        raise RuntimeError("Database connection pool not initialized. Call initialize_pool() first.")

    try:
        conn = _connection_pool.getconn()
        conn.cursor_factory = RealDictCursor
        return conn
    except Exception as e:
        logger.error(f"Error getting database connection: {e}")
        raise


def return_db_connection(conn):
    """Return a connection to the pool.

    Args:
        conn: psycopg2 connection object
    """
    global _connection_pool

    if _connection_pool is not None:
        _connection_pool.putconn(conn)


def initialize_pool(min_conn: int = 1, max_conn: int = 10):
    """Initialize the database connection pool.

    Args:
        min_conn: Minimum number of connections
        max_conn: Maximum number of connections
    """
    global _connection_pool

    settings = get_settings()

    try:
        _connection_pool = pool.SimpleConnectionPool(
            min_conn,
            max_conn,
            settings.DATABASE_URL
        )
        logger.info(f"Database connection pool initialized (min={min_conn}, max={max_conn})")

        # Register UUID adapter for psycopg2
        register_uuid()
        logger.info("UUID adapter registered for PostgreSQL")

        # Test connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        return_db_connection(conn)
        logger.info("Database connection test successful")

    except Exception as e:
        logger.error(f"Error initializing database pool: {e}")
        raise


def close_db_connection():
    """Close all connections in the pool."""
    global _connection_pool

    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Database connection pool closed")

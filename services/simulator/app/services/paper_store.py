"""Database-backed storage for paper trades."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, List, Optional
from uuid import UUID

from psycopg2.extras import RealDictCursor

from ..db.connection import get_db_connection, return_db_connection


@dataclass
class StoredLeg:
    identifier: Optional[str]
    strike: float
    option_type: str
    expiry: str
    quantity: int
    side: str
    entry_price: Optional[float]


@dataclass
class StoredTrade:
    id: UUID
    symbol: str
    nickname: Optional[str]
    created_at: datetime
    legs: List[StoredLeg]


class PaperTradeStore:
    """Persist trades to Postgres."""

    def add_trade(self, symbol: str, nickname: Optional[str], legs: List[StoredLeg]) -> StoredTrade:
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                INSERT INTO paper_trades (symbol, nickname)
                VALUES (%s, %s)
                RETURNING id, symbol, nickname, created_at
                """,
                (symbol.upper(), nickname)
            )
            trade_row = cursor.fetchone()
            for leg in legs:
                cursor.execute(
                    """
                    INSERT INTO paper_trade_legs
                    (trade_id, identifier, strike, option_type, expiry_date, quantity, side, entry_price)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        trade_row["id"],
                        leg.identifier,
                        leg.strike,
                        leg.option_type,
                        date.fromisoformat(leg.expiry),
                        leg.quantity,
                        leg.side,
                        leg.entry_price,
                    )
                )
            conn.commit()
            return StoredTrade(
                id=trade_row["id"],
                symbol=trade_row["symbol"],
                nickname=trade_row["nickname"],
                created_at=trade_row["created_at"],
                legs=legs
            )
        finally:
            return_db_connection(conn)

    def list_trades(self) -> List[StoredTrade]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "SELECT id, symbol, nickname, created_at FROM paper_trades ORDER BY created_at DESC"
            )
            trades = cursor.fetchall()
            if not trades:
                return []
            trade_ids = [row["id"] for row in trades]
            cursor.execute(
                """
                SELECT trade_id, identifier, strike, option_type, expiry_date, quantity, side, entry_price
                FROM paper_trade_legs
                WHERE trade_id = ANY(%s)
                ORDER BY created_at
                """,
                (trade_ids,)
            )
            leg_rows = cursor.fetchall()
            legs_map: Dict[UUID, List[StoredLeg]] = {trade["id"]: [] for trade in trades}
            for row in leg_rows:
                legs_map.setdefault(row["trade_id"], []).append(
                    StoredLeg(
                        identifier=row["identifier"],
                        strike=float(row["strike"]),
                        option_type=row["option_type"],
                        expiry=row["expiry_date"].isoformat(),
                        quantity=row["quantity"],
                        side=row["side"],
                        entry_price=float(row["entry_price"]) if row["entry_price"] is not None else None
                    )
                )
            results: List[StoredTrade] = []
            for trade in trades:
                results.append(
                    StoredTrade(
                        id=trade["id"],
                        symbol=trade["symbol"],
                        nickname=trade["nickname"],
                        created_at=trade["created_at"],
                        legs=legs_map.get(trade["id"], [])
                    )
                )
            return results
        finally:
            return_db_connection(conn)

    def get_trade(self, trade_id: UUID) -> Optional[StoredTrade]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "SELECT id, symbol, nickname, created_at FROM paper_trades WHERE id = %s",
                (trade_id,)
            )
            trade = cursor.fetchone()
            if not trade:
                return None
            cursor.execute(
                """
                SELECT identifier, strike, option_type, expiry_date, quantity, side, entry_price
                FROM paper_trade_legs WHERE trade_id = %s ORDER BY created_at
                """,
                (trade_id,)
            )
            legs = [
                StoredLeg(
                    identifier=row["identifier"],
                    strike=float(row["strike"]),
                    option_type=row["option_type"],
                    expiry=row["expiry_date"].isoformat(),
                    quantity=row["quantity"],
                    side=row["side"],
                    entry_price=float(row["entry_price"]) if row["entry_price"] is not None else None
                )
                for row in cursor.fetchall()
            ]
            return StoredTrade(
                id=trade["id"],
                symbol=trade["symbol"],
                nickname=trade["nickname"],
                created_at=trade["created_at"],
                legs=legs
            )
        finally:
            return_db_connection(conn)

    def delete_trade(self, trade_id: UUID) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM paper_trades WHERE id = %s", (trade_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted
        finally:
            return_db_connection(conn)

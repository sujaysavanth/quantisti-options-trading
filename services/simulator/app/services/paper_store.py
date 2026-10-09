"""Database-backed storage for paper trades and the paper account."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence
from uuid import UUID

from psycopg2.extensions import cursor as TupleCursor
from psycopg2.extras import RealDictCursor

from ..db.connection import get_db_connection, return_db_connection
from .paper_settlement import STARTING_BALANCE


@dataclass
class StoredLeg:
    identifier: Optional[str]
    strike: float
    option_type: str
    expiry: str
    quantity: int
    side: str
    entry_price: Optional[float]
    exit_price: Optional[float] = None
    id: Optional[UUID] = None


@dataclass
class StoredTrade:
    id: UUID
    symbol: str
    nickname: Optional[str]
    created_at: datetime
    legs: List[StoredLeg]
    status: str = "open"
    closed_at: Optional[datetime] = None
    close_reason: Optional[str] = None

    @property
    def expiry(self) -> Optional[str]:
        """The earliest leg expiry: the trade settles then."""
        return min((leg.expiry for leg in self.legs), default=None)


def _leg(row) -> StoredLeg:
    return StoredLeg(
        identifier=row["identifier"], strike=float(row["strike"]), option_type=row["option_type"],
        expiry=row["expiry_date"].isoformat(), quantity=row["quantity"], side=row["side"],
        entry_price=float(row["entry_price"]) if row["entry_price"] is not None else None,
        exit_price=float(row["exit_price"]) if row["exit_price"] is not None else None, id=row["id"])


def _trade(row, legs: List[StoredLeg]) -> StoredTrade:
    return StoredTrade(id=row["id"], symbol=row["symbol"], nickname=row["nickname"], created_at=row["created_at"],
                       legs=legs, status=row["status"], closed_at=row["closed_at"], close_reason=row["close_reason"])


TRADE_COLUMNS = "id, symbol, nickname, created_at, status, closed_at, close_reason"
LEG_COLUMNS = "id, trade_id, identifier, strike, option_type, expiry_date, quantity, side, entry_price, exit_price"


class PaperTradeStore:
    """Persist trades to Postgres."""

    def add_trade(self, symbol: str, nickname: Optional[str], legs: List[StoredLeg]) -> StoredTrade:
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(f"INSERT INTO paper_trades (symbol, nickname) VALUES (%s, %s) RETURNING {TRADE_COLUMNS}",
                           (symbol.upper(), nickname))
            trade_row = cursor.fetchone()
            for leg in legs:
                cursor.execute(
                    """
                    INSERT INTO paper_trade_legs
                    (trade_id, identifier, strike, option_type, expiry_date, quantity, side, entry_price)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (trade_row["id"], leg.identifier, leg.strike, leg.option_type, date.fromisoformat(leg.expiry),
                     leg.quantity, leg.side, leg.entry_price))
            conn.commit()
            return _trade(trade_row, legs)
        finally:
            return_db_connection(conn)

    def list_trades(self, status: Optional[str] = None) -> List[StoredTrade]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            where, params = ("WHERE status = %s", (status,)) if status else ("", ())
            cursor.execute(f"SELECT {TRADE_COLUMNS} FROM paper_trades {where} ORDER BY created_at DESC", params)
            trades = cursor.fetchall()
            if not trades:
                return []
            cursor.execute(f"SELECT {LEG_COLUMNS} FROM paper_trade_legs WHERE trade_id = ANY(%s) ORDER BY created_at",
                           ([row["id"] for row in trades],))
            legs_map: Dict[UUID, List[StoredLeg]] = {trade["id"]: [] for trade in trades}
            for row in cursor.fetchall():
                legs_map.setdefault(row["trade_id"], []).append(_leg(row))
            return [_trade(trade, legs_map.get(trade["id"], [])) for trade in trades]
        finally:
            return_db_connection(conn)

    def get_trade(self, trade_id: UUID) -> Optional[StoredTrade]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(f"SELECT {TRADE_COLUMNS} FROM paper_trades WHERE id = %s", (trade_id,))
            trade = cursor.fetchone()
            if not trade:
                return None
            cursor.execute(f"SELECT {LEG_COLUMNS} FROM paper_trade_legs WHERE trade_id = %s ORDER BY created_at", (trade_id,))
            return _trade(trade, [_leg(row) for row in cursor.fetchall()])
        finally:
            return_db_connection(conn)

    def close_trade(self, trade_id: UUID, exit_prices: Sequence[float], reason: str, closed_at: datetime) -> bool:
        """Record exit prices (in leg order) and close the trade. False if it was already closed."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=TupleCursor)     # the pool's default is RealDictCursor
            cursor.execute("""UPDATE paper_trades SET status = 'closed', closed_at = %s, close_reason = %s
                              WHERE id = %s AND status = 'open'""", (closed_at, reason, trade_id))
            if cursor.rowcount == 0:
                conn.rollback()
                return False
            cursor.execute("SELECT id FROM paper_trade_legs WHERE trade_id = %s ORDER BY created_at", (trade_id,))
            for (leg_id,), price in zip(cursor.fetchall(), exit_prices):
                cursor.execute("UPDATE paper_trade_legs SET exit_price = %s WHERE id = %s", (price, leg_id))
            conn.commit()
            return True
        finally:
            return_db_connection(conn)

    def starting_balance(self) -> float:
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=TupleCursor)     # the pool's default is RealDictCursor
            cursor.execute("SELECT starting_balance FROM paper_account WHERE id = 1")
            row = cursor.fetchone()
            return float(row[0]) if row else STARTING_BALANCE
        finally:
            return_db_connection(conn)

    def close_on(self, day: date, symbol: str = "SPX") -> Optional[float]:
        """The official close of `symbol` on `day` (underlying_daily), if it has arrived."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=TupleCursor)     # the pool's default is RealDictCursor
            cursor.execute("SELECT close FROM underlying_daily WHERE symbol = %s AND date = %s", (symbol, day))
            row = cursor.fetchone()
            return float(row[0]) if row else None
        finally:
            return_db_connection(conn)

    def delete_trade(self, trade_id: UUID) -> bool:
        """Delete an open trade (a mistake). Closed trades are kept: their P&L is part of the account."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=TupleCursor)     # the pool's default is RealDictCursor
            cursor.execute("DELETE FROM paper_trades WHERE id = %s AND status = 'open'", (trade_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted
        finally:
            return_db_connection(conn)

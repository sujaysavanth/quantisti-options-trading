"""Portfolio snapshots: build one from the simulator's paper trades and store it in portfolio_snapshots (schema 013).

The account figures are summed from the same GET /v1/paper/orders response as the positions, so a snapshot's
value and its positions always agree (the simulator's /v1/paper/account would mark the trades a second time);
only the starting balance comes from /v1/paper/account.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import Json

from ..clients import MarketStreamClient, SimulatorClient
from ..db.connection import get_db_connection, return_db_connection
from .positions import net_positions
from .schedule import Due, due

logger = logging.getLogger(__name__)


@dataclass
class Snapshot:
    kind: str
    taken_at: datetime
    observed_at: datetime
    session: date
    starting_balance: float
    account_value: float
    realised_pnl: float
    unrealised_pnl: float
    capital_held: float
    available: float
    open_trades: int
    closed_trades: int
    spot: Optional[float]
    positions: List[Dict[str, Any]] = field(default_factory=list)


def build(slot: Due, starting_balance: float, trades: List[dict], spot: Optional[float], now: datetime) -> Snapshot:
    """Same arithmetic as the simulator's account_summary, over one set of marks."""
    open_ = [t for t in trades if t["status"] == "open"]
    closed = [t for t in trades if t["status"] == "closed"]
    realised = sum(float(t["pnl"]) for t in closed)
    unrealised = sum(float(t["pnl"]) for t in open_)
    held = sum(float(t.get("capital_held") or 0.0) for t in open_)
    return Snapshot(
        kind=slot.kind, taken_at=slot.taken_at, observed_at=now, session=slot.session,
        starting_balance=starting_balance, account_value=starting_balance + realised + unrealised,
        realised_pnl=realised, unrealised_pnl=unrealised, capital_held=held,
        available=starting_balance + realised - held, open_trades=len(open_), closed_trades=len(closed),
        spot=spot, positions=net_positions(open_))


class SnapshotStore:
    COLUMNS = ("kind", "taken_at", "observed_at", "session", "starting_balance", "account_value", "realised_pnl",
               "unrealised_pnl", "capital_held", "available", "open_trades", "closed_trades", "spot", "positions")

    def exists(self, kind: str, taken_at: datetime) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM portfolio_snapshots WHERE kind = %s AND taken_at = %s", (kind, taken_at))
                return cur.fetchone() is not None
        finally:
            return_db_connection(conn)

    def save(self, snap: Snapshot) -> bool:
        """Insert unless that (kind, taken_at) is already stored. True if a row was written."""
        row = asdict(snap)
        row["positions"] = Json(row["positions"])
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO portfolio_snapshots ({', '.join(self.COLUMNS)}) "
                    f"VALUES ({', '.join(['%s'] * len(self.COLUMNS))}) ON CONFLICT (kind, taken_at) DO NOTHING",
                    [row[c] for c in self.COLUMNS])
                written = cur.rowcount == 1
            conn.commit()
            return written
        except Exception:
            conn.rollback()
            raise
        finally:
            return_db_connection(conn)

    def list(self, kind: Optional[str], start: Optional[date], end: Optional[date], with_positions: bool) -> List[dict]:
        cols = [c for c in self.COLUMNS if with_positions or c != "positions"]
        where, args = [], []
        if kind:
            where.append("kind = %s")
            args.append(kind)
        if start:
            where.append("session >= %s")
            args.append(start)
        if end:
            where.append("session <= %s")
            args.append(end)
        sql = f"SELECT {', '.join(cols)} FROM portfolio_snapshots"
        if where:
            sql += " WHERE " + " AND ".join(where)
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql + " ORDER BY taken_at, kind", args)
                rows = cur.fetchall()
        finally:
            return_db_connection(conn)
        numeric = {"starting_balance", "account_value", "realised_pnl", "unrealised_pnl", "capital_held", "available", "spot"}
        return [{k: (float(v) if k in numeric and v is not None else v) for k, v in dict(r).items()} for r in rows]


async def take_due(store: SnapshotStore, simulator: SimulatorClient, stream: MarketStreamClient,
                   now: Optional[datetime] = None) -> Optional[Snapshot]:
    """Take the snapshot due now if it isn't stored yet. Returns it, or None (nothing due, already taken, or the
    simulator didn't answer: the next check retries)."""
    now = now or datetime.now(timezone.utc)
    slot = due(now)
    if slot is None or store.exists(slot.kind, slot.taken_at):
        return None
    account, trades = await simulator.account(), await simulator.orders()
    if account is None or trades is None:
        return None
    snap = build(slot, float(account["starting_balance"]), trades, await stream.spot(), now)
    if store.save(snap):
        logger.info("portfolio %s snapshot %s: value %.2f, %d open", snap.kind, snap.taken_at, snap.account_value,
                    snap.open_trades)
        return snap
    return None

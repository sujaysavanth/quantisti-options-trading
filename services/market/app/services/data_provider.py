"""Data provider service for fetching and generating market data."""

import logging
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from psycopg2.extras import RealDictCursor

from .. import market_spec
from ..config import get_settings
from ..db.connection import get_db_connection, return_db_connection
from ..models.market_data import CandleData
from .chains import Quote, build_snapshot_chain, build_synthetic_chain

logger = logging.getLogger(__name__)

DEFAULT_VIX = 18.0  # long-run average, used only if no VIX row exists for a date


class DataProvider:
    """Provider for underlying data and option chains."""

    def __init__(self):
        self.settings = get_settings()
        self.symbol = market_spec.SYMBOL

    @contextmanager
    def _cursor(self) -> Iterator[RealDictCursor]:
        conn = get_db_connection()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield cur
            finally:
                cur.close()
        finally:
            return_db_connection(conn)

    # ------------------------------------------------------------ underlying

    def get_historical_data(self, start_date: date, end_date: date) -> List[CandleData]:
        """Daily candles for the underlying between two dates, inclusive."""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT date, open, high, low, close, volume, historical_volatility
                FROM underlying_daily
                WHERE symbol = %s AND date >= %s AND date <= %s
                ORDER BY date ASC
                """,
                (self.symbol, start_date, end_date),
            )
            rows = cur.fetchall()

        return [
            CandleData(
                date=row["date"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
                historical_volatility=float(row["historical_volatility"]) if row["historical_volatility"] else None,
            )
            for row in rows
        ]

    def get_latest_spot_price(self) -> Optional[Dict[str, Any]]:
        """Latest close, with the change from the previous close."""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT date, close, volume, historical_volatility
                FROM underlying_daily
                WHERE symbol = %s
                ORDER BY date DESC
                LIMIT 2
                """,
                (self.symbol,),
            )
            rows = cur.fetchall()

        if not rows:
            return None
        latest = rows[0]
        price = float(latest["close"])
        change = price - float(rows[1]["close"]) if len(rows) > 1 else None
        return {
            "date": latest["date"],
            "price": price,
            "volume": int(latest["volume"]),
            "historical_volatility": float(latest["historical_volatility"]) if latest["historical_volatility"] else None,
            "change": change,
            "change_percent": change / (price - change) * 100 if change is not None else None,
        }

    def get_spot_price_for_date(self, target_date: date) -> Optional[float]:
        """Close on `target_date`, or None if it was not a trading day / not loaded."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT close FROM underlying_daily WHERE symbol = %s AND date = %s",
                (self.symbol, target_date),
            )
            row = cur.fetchone()
        return float(row["close"]) if row else None

    # ------------------------------------------------------------ pricing inputs

    def get_rate(self, on: date) -> float:
        """Most recent T-bill rate on or before `on` (FRED publishes with a lag)."""
        with self._cursor() as cur:
            cur.execute("SELECT rate FROM rates_daily WHERE date <= %s ORDER BY date DESC LIMIT 1", (on,))
            row = cur.fetchone()
        return float(row["rate"]) if row else market_spec.FALLBACK_RATE

    def get_vix(self, on: date) -> float:
        """VIX close on or before `on`."""
        with self._cursor() as cur:
            cur.execute("SELECT close FROM vix_daily WHERE date <= %s ORDER BY date DESC LIMIT 1", (on,))
            row = cur.fetchone()
        if not row:
            logger.warning("No VIX data on or before %s; using %.1f", on, DEFAULT_VIX)
            return DEFAULT_VIX
        return float(row["close"])

    def get_vix_history(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT date, close FROM vix_daily WHERE date >= %s AND date <= %s ORDER BY date",
                (start_date, end_date),
            )
            return [{"date": r["date"], "close": float(r["close"])} for r in cur.fetchall()]

    def get_snapshot_quotes(self, on: date, expiry: date) -> List[Dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT strike, option_type, bid, ask, last, open_interest, volume, underlying_price
                FROM option_chain_snapshots
                WHERE symbol = %s AND snapshot_date = %s AND expiry_date = %s
                """,
                (self.symbol, on, expiry),
            )
            return cur.fetchall()

    # ------------------------------------------------------------ option chain

    def default_expiry(self, target_date: date, now: Optional[datetime] = None) -> date:
        """Nearest expiry that still has time left at the chain's valuation time."""
        as_of = market_spec.valuation_time(target_date, now)
        expiry = market_spec.next_expiry(target_date)
        if market_spec.year_fraction(as_of, expiry) > 0:
            return expiry
        return market_spec.next_expiry(target_date, min_dte=1)

    def generate_option_chain(
        self,
        target_date: Optional[date] = None,
        expiry_date: Optional[date] = None,
        strike_range: int = 10,
        now: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Option chain for `target_date` (default: latest loaded day).

        Uses a collected snapshot of listed quotes when one exists for that day
        and expiry; otherwise prices the chain with Black-Scholes from the close,
        VIX and the T-bill rate.
        """
        if target_date is None:
            spot_data = self.get_latest_spot_price()
            if not spot_data:
                return None
            spot, target_date = spot_data["price"], spot_data["date"]
        else:
            spot = self.get_spot_price_for_date(target_date)
            if spot is None:
                return None

        if expiry_date is None:
            expiry_date = self.default_expiry(target_date, now)
        elif not market_spec.is_expiry(expiry_date):
            raise ValueError(f"{expiry_date} is not a listed {self.symbol} expiry")

        as_of = market_spec.valuation_time(target_date, now or datetime.now(timezone.utc))
        T = market_spec.year_fraction(as_of, expiry_date)
        if T <= 0:
            logger.warning("Expiry %s has no time left as of %s", expiry_date, as_of)
            return None

        rate = self.get_rate(target_date)

        rows = self.get_snapshot_quotes(target_date, expiry_date)
        if rows:
            quotes = [
                Quote(
                    strike=float(r["strike"]),
                    option_type=r["option_type"],
                    bid=float(r["bid"]) if r["bid"] is not None else None,
                    ask=float(r["ask"]) if r["ask"] is not None else None,
                    last=float(r["last"]) if r["last"] is not None else None,
                    open_interest=r["open_interest"],
                    volume=r["volume"],
                )
                for r in rows
            ]
            chain = build_snapshot_chain(quotes, spot, target_date, expiry_date, T, rate, strike_range)
            if chain:
                return chain
            logger.warning("Snapshot for %s/%s unusable; falling back to synthetic", target_date, expiry_date)

        return build_synthetic_chain(spot, target_date, expiry_date, T, rate, self.get_vix(target_date), strike_range)

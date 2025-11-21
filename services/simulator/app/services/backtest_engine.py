"""Backtesting engine for option strategies."""

import logging
from datetime import date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

from psycopg2.extras import RealDictCursor

from ..db.connection import get_db_connection, return_db_connection
from ..services.market_client import MarketDataClient
from ..models.backtest import EntryLogic, ExitLogic, TradeStatus
from ..config import get_settings

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Engine to execute option strategy backtests."""

    def __init__(self):
        self.settings = get_settings()
        self.market_client = MarketDataClient()

    async def run_backtest(self, backtest_id: UUID):
        """Execute a backtest.

        Args:
            backtest_id: ID of backtest to run
        """
        conn = None
        try:
            # Update status to RUNNING
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute(
                """
                UPDATE backtests
                SET status = 'RUNNING', started_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (backtest_id,)
            )
            backtest = cursor.fetchone()
            conn.commit()
            cursor.close()
            return_db_connection(conn)
            conn = None

            if not backtest:
                raise ValueError(f"Backtest {backtest_id} not found")

            # Get strategy legs
            strategy_legs = self._get_strategy_legs(backtest['strategy_id'])

            # Generate trade dates based on entry logic
            trade_dates = self._generate_trade_dates(
                backtest['start_date'],
                backtest['end_date'],
                backtest['entry_logic']
            )

            logger.info(f"Running backtest {backtest_id} with {len(trade_dates)} trades")

            # Execute trades
            capital = float(backtest['initial_capital'])
            trade_number = 1

            for entry_date in trade_dates:
                # Execute trade
                trade_result = await self._execute_trade(
                    backtest_id=backtest_id,
                    trade_number=trade_number,
                    entry_date=entry_date,
                    strategy_legs=strategy_legs,
                    exit_logic=backtest['exit_logic'],
                    stop_loss_pct=backtest.get('stop_loss_pct'),
                    target_pct=backtest.get('target_pct'),
                    max_holding_days=backtest.get('max_holding_days')
                )

                if trade_result:
                    trade_number += 1

            # Update status to COMPLETED
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE backtests
                SET status = 'COMPLETED', completed_at = now()
                WHERE id = %s
                """,
                (backtest_id,)
            )
            conn.commit()
            cursor.close()
            return_db_connection(conn)
            conn = None

            logger.info(f"Backtest {backtest_id} completed successfully")

        except Exception as e:
            logger.error(f"Error running backtest {backtest_id}: {e}")

            # Update status to FAILED
            if conn is None:
                conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE backtests
                SET status = 'FAILED', error_message = %s, completed_at = now()
                WHERE id = %s
                """,
                (str(e), backtest_id)
            )
            conn.commit()
            cursor.close()
            return_db_connection(conn)
            raise

        finally:
            if conn:
                return_db_connection(conn)

    def _get_strategy_legs(self, strategy_id: UUID) -> List[Dict[str, Any]]:
        """Get strategy legs from database."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT * FROM strategy_legs
                WHERE strategy_id = %s
                ORDER BY leg_order
                """,
                (strategy_id,)
            )
            legs = cursor.fetchall()
            cursor.close()
            return legs
        finally:
            return_db_connection(conn)

    def _generate_trade_dates(
        self,
        start_date: date,
        end_date: date,
        entry_logic: str
    ) -> List[date]:
        """Generate trade entry dates based on entry logic."""
        dates = []
        current_date = start_date

        if entry_logic == EntryLogic.ON_DATE.value:
            # Single trade on start date
            dates.append(start_date)

        elif entry_logic == EntryLogic.DAILY.value:
            # Daily trades
            while current_date <= end_date:
                # Skip weekends (assuming market is closed on Sat/Sun)
                if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
                    dates.append(current_date)
                current_date += timedelta(days=1)

        elif entry_logic == EntryLogic.WEEKLY.value:
            # Weekly trades (every Monday)
            while current_date <= end_date:
                if current_date.weekday() == 0:  # Monday
                    dates.append(current_date)
                current_date += timedelta(days=1)

        elif entry_logic == EntryLogic.MONTHLY.value:
            # Monthly trades (first trading day of month)
            while current_date <= end_date:
                if current_date.day == 1 or (current_date == start_date):
                    dates.append(current_date)
                # Jump to next month
                if current_date.month == 12:
                    current_date = date(current_date.year + 1, 1, 1)
                else:
                    current_date = date(current_date.year, current_date.month + 1, 1)

        return dates

    async def _execute_trade(
        self,
        backtest_id: UUID,
        trade_number: int,
        entry_date: date,
        strategy_legs: List[Dict[str, Any]],
        exit_logic: str,
        stop_loss_pct: Optional[float],
        target_pct: Optional[float],
        max_holding_days: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """Execute a single trade."""
        try:
            # Get spot price on entry date
            entry_spot = await self.market_client.get_spot_price(entry_date)
            if not entry_spot:
                logger.warning(f"No spot price for {entry_date}, skipping trade")
                return None

            # Calculate ATM strike
            atm_strike = round(entry_spot / 50) * 50

            # Build positions for each leg
            trade_legs = []
            total_premium = 0.0
            
            # Determine the main expiry date for the trade (usually the first leg's expiry or nearest)
            # We'll use the first leg's expiry as the "trade expiry" for database purposes
            trade_expiry_date = None

            for leg in strategy_legs:
                # Calculate strike based on offset
                strike = atm_strike + leg['strike_offset']

                # Calculate expiry date for this leg
                expiry_offset = leg.get('expiry_offset', 0)
                leg_expiry_date = self._get_expiry(entry_date, expiry_offset)
                
                if trade_expiry_date is None:
                    trade_expiry_date = leg_expiry_date

                # Get option price
                option_data = await self.market_client.get_option_price(
                    strike=strike,
                    option_type=leg['option_type'],
                    target_date=entry_date,
                    expiry_date=leg_expiry_date
                )

                if not option_data:
                    logger.warning(f"No option data for {strike} {leg['option_type']} {leg_expiry_date}, skipping trade")
                    return None

                price = float(option_data['price'])
                quantity = int(leg['quantity']) * self.settings.NIFTY_LOT_SIZE

                # Calculate premium (BUY = debit, SELL = credit)
                if leg['action'] == 'BUY':
                    total_premium -= price * quantity
                else:  # SELL
                    total_premium += price * quantity

                trade_legs.append({
                    'action': leg['action'],
                    'option_type': leg['option_type'],
                    'strike': strike,
                    'expiry_date': leg_expiry_date,
                    'quantity': quantity,
                    'entry_price': price,
                    'entry_iv': option_data.get('implied_volatility')
                })

            # Save trade to database
            trade_id = self._save_trade(
                backtest_id=backtest_id,
                trade_number=trade_number,
                entry_date=entry_date,
                expiry_date=trade_expiry_date,
                entry_spot_price=entry_spot,
                entry_premium=total_premium,
                trade_legs=trade_legs
            )

            # Simulate holding and exit
            exit_result = await self._simulate_exit(
                trade_id=trade_id,
                entry_date=entry_date,
                expiry_date=expiry_date,
                entry_premium=total_premium,
                trade_legs=trade_legs,
                exit_logic=exit_logic,
                stop_loss_pct=stop_loss_pct,
                target_pct=target_pct,
                max_holding_days=max_holding_days
            )

            return exit_result

        except Exception as e:
            logger.error(f"Error executing trade {trade_number}: {e}")
            return None

    def _get_expiry(self, current_date: date, offset_weeks: int = 0) -> date:
        """Calculate the Nifty weekly expiry (Tuesday) with offset."""
        # Find the next Tuesday
        days_until_tuesday = (1 - current_date.weekday()) % 7
        if days_until_tuesday == 0:
            next_expiry = current_date
        else:
            next_expiry = current_date + timedelta(days=days_until_tuesday)
        
        # Add offset weeks
        return next_expiry + timedelta(weeks=offset_weeks)

    def _get_next_expiry(self, current_date: date) -> date:
        """Legacy method for backward compatibility."""
        return self._get_expiry(current_date, 0)

    def _save_trade(
        self,
        backtest_id: UUID,
        trade_number: int,
        entry_date: date,
        expiry_date: date,
        entry_spot_price: float,
        entry_premium: float,
        trade_legs: List[Dict[str, Any]]
    ) -> UUID:
        """Save trade to database."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Insert trade
            cursor.execute(
                """
                INSERT INTO backtest_trades
                (backtest_id, trade_number, entry_date, expiry_date, entry_spot_price, entry_premium, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'OPEN')
                RETURNING id
                """,
                (backtest_id, trade_number, entry_date, expiry_date, entry_spot_price, entry_premium)
            )
            trade_id = cursor.fetchone()['id']

            # Insert trade legs
            for leg in trade_legs:
                cursor.execute(
                    """
                    INSERT INTO backtest_trade_legs
                    (trade_id, action, option_type, strike, expiry_date, quantity, entry_price, entry_iv)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        trade_id, leg['action'], leg['option_type'], leg['strike'],
                        leg['expiry_date'], leg['quantity'], leg['entry_price'], leg.get('entry_iv')
                    )
                )

            conn.commit()
            cursor.close()
            return trade_id

        finally:
            return_db_connection(conn)

    async def _simulate_exit(
        self,
        trade_id: UUID,
        entry_date: date,
        expiry_date: date,
        entry_premium: float,
        trade_legs: List[Dict[str, Any]],
        exit_logic: str,
        stop_loss_pct: Optional[float],
        target_pct: Optional[float],
        max_holding_days: Optional[int]
    ) -> Dict[str, Any]:
        """Simulate trade exit based on exit logic."""
        current_date = entry_date + timedelta(days=1)
        exit_date = None
        exit_reason = None

        # Find the nearest expiry among all legs
        # For Calendar spreads, we usually exit when the near leg expires
        nearest_expiry = min(leg['expiry_date'] for leg in trade_legs)

        # For simplicity, exit on nearest expiry
        # TODO: Implement daily checks for stop loss, target, max days
        if exit_logic == ExitLogic.ON_EXPIRY.value or True:  # Default to expiry for now
            exit_date = nearest_expiry
            exit_reason = "EXPIRY"

        # Get exit prices
        exit_spot = await self.market_client.get_spot_price(exit_date)
        if not exit_spot:
            exit_spot = entry_premium  # Fallback

        # Calculate exit premium
        exit_premium = 0.0
        for leg in trade_legs:
            # If this leg is expiring today, use intrinsic value
            if leg['expiry_date'] == exit_date:
                if leg['option_type'] == 'CE':
                    exit_price = max(exit_spot - leg['strike'], 0)
                else:  # PE
                    exit_price = max(leg['strike'] - exit_spot, 0)
            else:
                # If leg is NOT expiring (e.g. far leg of calendar), get market price
                option_data = await self.market_client.get_option_price(
                    strike=leg['strike'],
                    option_type=leg['option_type'],
                    target_date=exit_date,
                    expiry_date=leg['expiry_date']
                )
                if option_data:
                    exit_price = float(option_data['price'])
                else:
                    # Fallback if data missing (shouldn't happen for liquid Nifty)
                    # Use Black-Scholes or intrinsic as worst case
                    if leg['option_type'] == 'CE':
                        exit_price = max(exit_spot - leg['strike'], 0)
                    else:  # PE
                        exit_price = max(leg['strike'] - exit_spot, 0)

            # Calculate exit premium (opposite of entry)
            if leg['action'] == 'BUY':
                exit_premium += exit_price * leg['quantity']
            else:  # SELL
                exit_premium -= exit_price * leg['quantity']

        # Calculate P&L
        pnl = entry_premium + exit_premium
        pnl_pct = (pnl / abs(entry_premium) * 100) if entry_premium != 0 else 0
        holding_days = (exit_date - entry_date).days

        # Update trade in database
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE backtest_trades
                SET exit_date = %s, exit_spot_price = %s, exit_premium = %s,
                    pnl = %s, pnl_pct = %s, status = 'CLOSED', exit_reason = %s,
                    holding_days = %s, closed_at = now()
                WHERE id = %s
                """,
                (exit_date, exit_spot, exit_premium, pnl, pnl_pct, exit_reason, holding_days, trade_id)
            )
            conn.commit()
            cursor.close()

        finally:
            return_db_connection(conn)

        return {
            'trade_id': trade_id,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_date': exit_date,
            'exit_reason': exit_reason
        }

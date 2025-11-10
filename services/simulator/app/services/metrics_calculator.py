"""Calculate performance metrics for backtests."""

import logging
import math
from typing import List, Dict, Any, Optional
from uuid import UUID

import numpy as np
from psycopg2.extras import RealDictCursor

from ..db.connection import get_db_connection, return_db_connection

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculator for backtest performance metrics."""

    def calculate_metrics(self, backtest_id: UUID) -> Dict[str, Any]:
        """Calculate all metrics for a backtest.

        Args:
            backtest_id: ID of backtest

        Returns:
            Dictionary with all calculated metrics
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get backtest info
            cursor.execute(
                "SELECT * FROM backtests WHERE id = %s",
                (backtest_id,)
            )
            backtest = cursor.fetchone()

            if not backtest:
                raise ValueError(f"Backtest {backtest_id} not found")

            # Get all trades
            cursor.execute(
                """
                SELECT * FROM backtest_trades
                WHERE backtest_id = %s AND status = 'CLOSED'
                ORDER BY entry_date
                """,
                (backtest_id,)
            )
            trades = cursor.fetchall()
            cursor.close()

            if not trades:
                logger.warning(f"No closed trades found for backtest {backtest_id}")
                return self._empty_metrics(backtest_id, backtest['initial_capital'])

            # Calculate metrics
            metrics = self._calculate_all_metrics(
                trades=trades,
                initial_capital=float(backtest['initial_capital'])
            )

            # Save metrics to database
            self._save_metrics(backtest_id, metrics)

            return metrics

        finally:
            return_db_connection(conn)

    def _calculate_all_metrics(
        self,
        trades: List[Dict[str, Any]],
        initial_capital: float
    ) -> Dict[str, Any]:
        """Calculate all performance metrics."""
        # Basic trade statistics
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if float(t['pnl']) > 0)
        losing_trades = sum(1 for t in trades if float(t['pnl']) < 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # P&L statistics
        pnls = [float(t['pnl']) for t in trades]
        total_pnl = sum(pnls)
        avg_pnl_per_trade = total_pnl / total_trades if total_trades > 0 else 0

        # Max profit/loss
        max_profit = max(pnls) if pnls else 0
        max_loss = min(pnls) if pnls else 0

        # Drawdown calculation
        cumulative_pnls = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative_pnls)
        drawdowns = running_max - cumulative_pnls
        max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0
        max_drawdown_pct = (max_drawdown / initial_capital * 100) if initial_capital > 0 else 0

        # Profit factor
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

        # Sharpe ratio
        sharpe_ratio = self._calculate_sharpe_ratio(pnls)

        # Sortino ratio
        sortino_ratio = self._calculate_sortino_ratio(pnls)

        # Holding days
        holding_days = [int(t['holding_days']) for t in trades if t.get('holding_days')]
        avg_holding_days = sum(holding_days) / len(holding_days) if holding_days else 0

        # Final capital and return
        final_capital = initial_capital + total_pnl
        total_return_pct = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'avg_pnl_per_trade': round(avg_pnl_per_trade, 2),
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'max_drawdown': round(-max_drawdown, 2),  # Negative for loss
            'max_drawdown_pct': round(-max_drawdown_pct, 4),  # Negative for loss
            'sharpe_ratio': round(sharpe_ratio, 4) if sharpe_ratio is not None else None,
            'sortino_ratio': round(sortino_ratio, 4) if sortino_ratio is not None else None,
            'profit_factor': round(profit_factor, 4) if profit_factor is not None else None,
            'avg_holding_days': round(avg_holding_days, 2),
            'final_capital': round(final_capital, 2),
            'total_return_pct': round(total_return_pct, 4)
        }

    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.065) -> Optional[float]:
        """Calculate Sharpe ratio.

        Args:
            returns: List of trade returns
            risk_free_rate: Annual risk-free rate (default 6.5%)

        Returns:
            Sharpe ratio or None if cannot calculate
        """
        if not returns or len(returns) < 2:
            return None

        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array, ddof=1)

        if std_return == 0:
            return None

        # Annualize (assuming ~252 trading days)
        # Daily risk-free rate
        daily_rf = risk_free_rate / 252

        sharpe = (mean_return - daily_rf) / std_return
        # Annualize Sharpe ratio
        sharpe_annual = sharpe * math.sqrt(252)

        return sharpe_annual

    def _calculate_sortino_ratio(self, returns: List[float], risk_free_rate: float = 0.065) -> Optional[float]:
        """Calculate Sortino ratio (uses downside deviation).

        Args:
            returns: List of trade returns
            risk_free_rate: Annual risk-free rate

        Returns:
            Sortino ratio or None if cannot calculate
        """
        if not returns or len(returns) < 2:
            return None

        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)

        # Calculate downside deviation (only negative returns)
        negative_returns = returns_array[returns_array < 0]
        if len(negative_returns) == 0:
            return None

        downside_dev = np.std(negative_returns, ddof=1)

        if downside_dev == 0:
            return None

        # Daily risk-free rate
        daily_rf = risk_free_rate / 252

        sortino = (mean_return - daily_rf) / downside_dev
        # Annualize Sortino ratio
        sortino_annual = sortino * math.sqrt(252)

        return sortino_annual

    def _empty_metrics(self, backtest_id: UUID, initial_capital: float) -> Dict[str, Any]:
        """Return empty metrics when no trades."""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'avg_pnl_per_trade': 0.0,
            'max_profit': 0.0,
            'max_loss': 0.0,
            'max_drawdown': 0.0,
            'max_drawdown_pct': 0.0,
            'sharpe_ratio': None,
            'sortino_ratio': None,
            'profit_factor': None,
            'avg_holding_days': 0.0,
            'final_capital': initial_capital,
            'total_return_pct': 0.0
        }

    def _save_metrics(self, backtest_id: UUID, metrics: Dict[str, Any]):
        """Save metrics to database."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Delete existing metrics if any
            cursor.execute(
                "DELETE FROM backtest_metrics WHERE backtest_id = %s",
                (backtest_id,)
            )

            # Insert new metrics
            cursor.execute(
                """
                INSERT INTO backtest_metrics
                (backtest_id, total_trades, winning_trades, losing_trades, win_rate,
                 total_pnl, avg_pnl_per_trade, max_profit, max_loss, max_drawdown,
                 max_drawdown_pct, sharpe_ratio, sortino_ratio, profit_factor,
                 avg_holding_days, final_capital, total_return_pct)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    backtest_id,
                    metrics['total_trades'],
                    metrics['winning_trades'],
                    metrics['losing_trades'],
                    metrics['win_rate'],
                    metrics['total_pnl'],
                    metrics['avg_pnl_per_trade'],
                    metrics['max_profit'],
                    metrics['max_loss'],
                    metrics['max_drawdown'],
                    metrics['max_drawdown_pct'],
                    metrics['sharpe_ratio'],
                    metrics['sortino_ratio'],
                    metrics['profit_factor'],
                    metrics['avg_holding_days'],
                    metrics['final_capital'],
                    metrics['total_return_pct']
                )
            )

            conn.commit()
            cursor.close()

        finally:
            return_db_connection(conn)

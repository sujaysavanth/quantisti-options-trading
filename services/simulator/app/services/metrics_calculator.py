"""Calculate performance metrics for backtests."""

import logging
import math
from typing import List, Dict, Any, Optional
from uuid import UUID

import numpy as np
from psycopg2.extras import RealDictCursor

from ..db.connection import get_db_connection, return_db_connection

logger = logging.getLogger(__name__)

# Annual risk-free rate for Sharpe/Sortino: roughly the recent 3-month US T-bill.
RISK_FREE_RATE = 0.04


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

        # Risk-adjusted returns: each trade's P&L as a return on capital, annualised
        # by how often trades were actually entered.
        returns = [p / initial_capital for p in pnls] if initial_capital > 0 else []
        periods_per_year = self._periods_per_year([t['entry_date'] for t in trades])
        sharpe_ratio = self._calculate_sharpe_ratio(returns, periods_per_year)
        sortino_ratio = self._calculate_sortino_ratio(returns, periods_per_year)

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

    @staticmethod
    def _periods_per_year(entry_dates: List[Any]) -> float:
        """Trades per year implied by the average gap between entries (weekly entries -> ~52)."""
        if len(entry_dates) < 2:
            return 52.0
        span_days = (max(entry_dates) - min(entry_dates)).days
        if span_days <= 0:
            return 252.0
        return 365.25 * (len(entry_dates) - 1) / span_days

    @staticmethod
    def _calculate_sharpe_ratio(returns: List[float], periods_per_year: float,
                                risk_free_rate: float = RISK_FREE_RATE) -> Optional[float]:
        """Annualised Sharpe ratio of per-trade returns on capital."""
        if len(returns) < 2:
            return None
        excess = np.array(returns) - risk_free_rate / periods_per_year
        std = float(np.std(excess, ddof=1))
        if std == 0:
            return None
        return float(np.mean(excess)) / std * math.sqrt(periods_per_year)

    @staticmethod
    def _calculate_sortino_ratio(returns: List[float], periods_per_year: float,
                                 risk_free_rate: float = RISK_FREE_RATE) -> Optional[float]:
        """Annualised Sortino ratio: excess return over downside deviation (below the risk-free rate)."""
        if len(returns) < 2:
            return None
        excess = np.array(returns) - risk_free_rate / periods_per_year
        downside = float(np.sqrt(np.mean(np.minimum(excess, 0.0) ** 2)))
        if downside == 0:
            return None
        return float(np.mean(excess)) / downside * math.sqrt(periods_per_year)

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
            metrics = {k: v.item() if isinstance(v, np.generic) else v for k, v in metrics.items()}

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

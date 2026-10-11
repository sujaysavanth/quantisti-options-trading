/**
 * The paper portfolio from the portfolio service (:8083, services/portfolio) and its risk from the stats service
 * (:8084, services/stats). Pure helpers below are tested in portfolio.test.ts.
 */

import { errorText } from './paper';

export const PORTFOLIO_API = process.env.NEXT_PUBLIC_PORTFOLIO_API ?? 'http://localhost:8083';
export const STATS_API = process.env.NEXT_PUBLIC_STATS_API ?? 'http://localhost:8084';

export type Snapshot = {
  kind: 'close' | 'intraday';
  taken_at: string;
  session: string;
  starting_balance: number;
  account_value: number;
  realised_pnl: number;
  unrealised_pnl: number;
  capital_held: number;
  available: number;
  open_trades: number;
  spot: number | null;
};

export type TradeBlock = {
  trades: number;
  total_pnl: number;
  win_rate: number | null;
  average_win: number | null;
  average_loss: number | null;
  profit_factor: number | null;
  expectancy: number | null;
  largest_win: number | null;
  largest_loss: number | null;
  median_holding_hours: number | null;
};

export type Performance = {
  starting_balance: number;
  equity: {
    sessions: number;
    returns: number;
    missing_sessions: number;
    total_return: number | null;
    period_return: number | null;
    volatility: number | null;
    sharpe: number | null;
    sortino: number | null;
    spx_return: number | null;
    beta: number | null;
    correlation: number | null;
    drawdown: { max_drawdown: number; current_drawdown: number; peak: string | null; trough: string | null } | null;
  };
  trades: TradeBlock & { by_strategy: Record<string, TradeBlock> };
  meaningful: boolean;
  notes: string[];
};

export type GreekTotals = { delta: number; gamma: number; vega: number; theta: number; delta_1pct: number; gamma_1pct: number };

export type Greeks = {
  spot: number;
  quoted_at: string | null;
  totals: GreekTotals;
  by_expiry: (GreekTotals & { expiry: string })[];
  positions: (GreekTotals & { expiry: string; strike: number; option_type: string; quantity: number; iv: number; iv_source: string })[];
  unpriced: { expiry: string; strike: number; option_type: string; reason: string }[];
};

export type StressRow = {
  name: string;
  date: string | null;
  spx_move: number;
  iv_shift: number;
  days: number;
  pnl: number;
  pct_of_account: number | null;
  account_value_after: number;
  capital_held_after: number | null;
  available_after: number | null;
  short_of_capital: boolean;
};

export type Stress = {
  spot: number;
  open_trades: number;
  axes: { spx_moves: number[]; iv_shifts: number[]; horizons_days: number[] };
  grid: StressRow[];
  historical: StressRow[];
  summary: Record<'grid' | 'historical', { worst: { name: string; pnl: number } | null; margin_calls: number }>;
  capital_available: boolean;
  unpriced: unknown[];
};

export type VarLevel = { var: number; es: number };
export type VarMethod = {
  levels: Record<string, VarLevel>;
  scenarios: number;
  sigma_now?: number;
  sigma_source?: 'garch' | 'ewma';
  sigma_long_run?: number;
  lookback_sessions?: number;
};
export type VarNow = { open_trades: number; account_value: number; methods: Record<string, VarMethod> };

export type VarTest = {
  method: string;
  confidence: number;
  kupiec: { observations: number; breaches: number; expected: number; p_value: number | null };
  christoffersen: { p_value: number | null };
  breach_days: string[];
};
export type VarHistory = { rows: unknown[]; tests: VarTest[]; note: string };

async function get<T>(base: string, path: string): Promise<T> {
  const response = await fetch(`${base}${path}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(await errorText(response));
  return (await response.json()) as T;
}

export const fetchPerformance = () => get<Performance>(PORTFOLIO_API, '/v1/portfolio/performance');
export const fetchEquity = (kind: 'close' | 'intraday') =>
  get<{ snapshots: Snapshot[] }>(PORTFOLIO_API, `/v1/portfolio/equity?kind=${kind}`).then((b) => b.snapshots);
export const fetchGreeks = () => get<Greeks>(STATS_API, '/v1/risk/greeks');
export const fetchStress = () => get<Stress>(STATS_API, '/v1/risk/stress');
export const fetchVar = () => get<VarNow>(STATS_API, '/v1/risk/var');
export const fetchVarHistory = () => get<VarHistory>(STATS_API, '/v1/risk/var/history');
export const tradesCsvUrl = (status: 'closed' | 'all' = 'all') => `${PORTFOLIO_API}/v1/portfolio/trades.csv?status=${status}`;

export type EquityPoint = { t: string; value: number; spx: number | null; drawdown: number };

/**
 * Account value over time with SPX rebased to the first point's account value (so the two lines start together and
 * the gap is the excess over holding the index), and the drawdown from the running peak. The starting balance is
 * the first peak, as in the portfolio service's max drawdown.
 */
export function equitySeries(snapshots: Snapshot[], startingBalance: number): EquityPoint[] {
  const pts = [...snapshots].sort((a, b) => a.taken_at.localeCompare(b.taken_at));
  const base = pts.find((p) => p.spot);
  let peak = startingBalance;
  return pts.map((p) => {
    peak = Math.max(peak, p.account_value);
    return {
      t: p.taken_at,
      value: p.account_value,
      spx: base && p.spot ? (pts[0].account_value * p.spot) / base.spot! : null,
      drawdown: p.account_value / peak - 1,
    };
  });
}

/** Stress grid as a matrix for one horizon: rows = IV shifts (largest first), columns = SPX moves. */
export function stressMatrix(stress: Stress, days: number): { ivShift: number; cells: StressRow[] }[] {
  const at = stress.grid.filter((r) => r.days === days);
  return [...stress.axes.iv_shifts]
    .sort((a, b) => b - a)
    .map((iv) => ({
      ivShift: iv,
      cells: stress.axes.spx_moves.map((m) => at.find((r) => r.iv_shift === iv && Math.abs(r.spx_move - m) < 1e-9)!),
    }));
}

/** Background for a P&L cell: green for gains, red for losses, stronger with size relative to `scale`. */
export function pnlTint(pnl: number, scale: number): string {
  if (!scale || Math.abs(pnl) < 0.5) return 'transparent';
  const a = Math.min(Math.abs(pnl) / scale, 1) * 0.55 + 0.08;
  return pnl > 0 ? `rgba(16, 185, 129, ${a.toFixed(3)})` : `rgba(244, 63, 94, ${a.toFixed(3)})`;
}

export const METHOD_LABELS: Record<string, string> = {
  historical: 'Historical (all days since 2010)',
  filtered_historical: 'Filtered historical (scaled to today’s vol)',
  delta_gamma_vega: 'Delta-gamma-vega (normal)',
};

/** "+1.23%" / "–" */
export const pct = (v: number | null | undefined, digits = 2) =>
  v == null ? '–' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(digits)}%`;

/** A ratio or "–" when the sample is too small (the service returns null). */
export const ratio = (v: number | null | undefined, digits = 2) => (v == null ? '–' : v.toFixed(digits));

'use client';

import { useEffect, useMemo, useState } from 'react';
import classNames from 'classnames';
import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { usd } from '@/data/format';
import { equitySeries, pct, ratio, type Performance, type Snapshot } from '@/data/portfolio';
import { Panel, PanelState, Stat, toneOf } from '@/components/Panel';

const tooltipStyle = { backgroundColor: '#0f172a', borderRadius: '1rem', border: '1px solid #1e293b', color: '#f8fafc' };
const when = (t: string, intraday: boolean) =>
  new Date(t).toLocaleString('en-US', {
    timeZone: 'America/New_York', month: 'short', day: 'numeric', ...(intraday ? { hour: 'numeric', minute: '2-digit' } : {}),
  });

interface Props {
  performance: Performance | null;
  snapshots: Record<'close' | 'intraday', Snapshot[] | null>;
  status: 'loading' | 'ready' | 'error';
}

/** Account value vs SPX, drawdown, and the performance stats from the portfolio service. */
export function EquityPanel({ performance, snapshots, status }: Props) {
  const [kind, setKind] = useState<'close' | 'intraday'>('close');
  const [isClient, setIsClient] = useState(false);
  useEffect(() => setIsClient(true), []);

  const series = useMemo(
    () => (performance && snapshots[kind] ? equitySeries(snapshots[kind]!, performance.starting_balance) : []),
    [performance, snapshots, kind],
  );

  const toggle = (
    <div className="inline-flex rounded-full bg-slate-100 p-1 dark:bg-slate-800">
      {(['close', 'intraday'] as const).map((k) => (
        <button
          key={k}
          onClick={() => setKind(k)}
          className={classNames('rounded-full px-3 py-1 text-xs', kind === k ? 'bg-white shadow dark:bg-slate-700' : 'text-slate-500')}
        >
          {k === 'close' ? 'Daily closes' : 'Every 15 min'}
        </button>
      ))}
    </div>
  );

  if (status !== 'ready' || !performance) {
    return <Panel eyebrow="Paper account" title="Performance"><PanelState status={status === 'error' ? 'error' : 'loading'} service="The portfolio service (8083)" /></Panel>;
  }
  const e = performance.equity;
  const t = performance.trades;

  return (
    <Panel eyebrow="Paper account" title="Performance" aside={toggle}>
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Total return" value={pct(e.total_return)} tone={toneOf(e.total_return)} hint="Since the account opened, from the $30,000 start" />
        <Stat label="SPX same days" value={pct(e.spx_return)} tone={toneOf(e.spx_return)} hint="Buy-and-hold over the sessions with a close snapshot" />
        <Stat label="Max drawdown" value={pct(e.drawdown?.max_drawdown ?? null)} tone={toneOf(e.drawdown?.max_drawdown)} />
        <Stat label="Sharpe" value={ratio(e.sharpe)} hint="Daily excess returns over the T-bill, annualised; needs 20 daily returns" />
        <Stat label="Sortino" value={ratio(e.sortino)} hint="Like Sharpe, but only downside volatility counts" />
        <Stat label="Beta to SPX" value={ratio(e.beta)} />
      </div>

      <div className="mt-6 h-64">
        {isClient && series.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={series}>
              <XAxis dataKey="t" tickFormatter={(v) => when(v, kind === 'intraday')} stroke="#94a3b8" minTickGap={40} />
              <YAxis yAxisId="v" tickFormatter={(v) => usd(v)} stroke="#94a3b8" domain={['auto', 'auto']} width={80} />
              <Tooltip
                contentStyle={tooltipStyle}
                labelFormatter={(v) => when(String(v), kind === 'intraday')}
                formatter={(v: number, name) => [usd(v), name === 'value' ? 'Account value' : 'SPX, rebased']}
              />
              <Line yAxisId="v" type="monotone" dataKey="spx" stroke="#94a3b8" strokeDasharray="4 4" dot={false} />
              <Line yAxisId="v" type="monotone" dataKey="value" stroke="#10b981" strokeWidth={3} dot={series.length < 30} />
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center justify-center rounded-2xl bg-slate-100 px-6 text-center text-sm text-slate-500 dark:bg-slate-800/40 dark:text-slate-400">
            No {kind === 'close' ? 'close' : 'intraday'} snapshots yet. The portfolio service takes one every 15 minutes in
            session and one about 20 minutes after each close.
          </div>
        )}
      </div>
      {series.length > 1 ? (
        <div className="mt-2 h-20">
          {isClient ? (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series}>
                <XAxis dataKey="t" hide />
                <YAxis tickFormatter={(v) => pct(v, 0)} stroke="#94a3b8" width={80} domain={['dataMin', 0]} />
                <Tooltip contentStyle={tooltipStyle} labelFormatter={(v) => when(String(v), kind === 'intraday')} formatter={(v: number) => [pct(v), 'Drawdown']} />
                <Area type="monotone" dataKey="drawdown" stroke="#f43f5e" fill="#f43f5e" fillOpacity={0.2} />
              </ComposedChart>
            </ResponsiveContainer>
          ) : null}
        </div>
      ) : null}

      <div className="mt-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Closed trades" value={t.trades} />
        <Stat label="Win rate" value={t.win_rate == null ? '–' : `${Math.round(t.win_rate * 100)}%`} />
        <Stat label="Profit factor" value={ratio(t.profit_factor)} hint="Gross wins / gross losses" />
        <Stat label="Expectancy" value={t.expectancy == null ? '–' : usd(t.expectancy)} tone={toneOf(t.expectancy)} hint="Average P&L per closed trade" />
        <Stat label="Average win" value={t.average_win == null ? '–' : usd(t.average_win)} tone="text-emerald-600 dark:text-emerald-400" />
        <Stat label="Average loss" value={t.average_loss == null ? '–' : usd(t.average_loss)} tone="text-rose-600 dark:text-rose-400" />
      </div>

      {Object.keys(t.by_strategy).length ? (
        <table className="mt-6 min-w-full text-sm">
          <thead className="text-xs uppercase text-slate-500">
            <tr>
              <th className="py-1 pr-3 text-left">Strategy</th>
              <th className="py-1 pr-3 text-right">Trades</th>
              <th className="py-1 pr-3 text-right">Win rate</th>
              <th className="py-1 pr-3 text-right">Total P&L</th>
              <th className="py-1 text-right">Median hold</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-500/20">
            {Object.entries(t.by_strategy).map(([name, b]) => (
              <tr key={name}>
                <td className="py-1.5 pr-3">{name}</td>
                <td className="py-1.5 pr-3 text-right tabular-nums">{b.trades}</td>
                <td className="py-1.5 pr-3 text-right tabular-nums">{b.win_rate == null ? '–' : `${Math.round(b.win_rate * 100)}%`}</td>
                <td className={`py-1.5 pr-3 text-right tabular-nums ${toneOf(b.total_pnl)}`}>{usd(b.total_pnl)}</td>
                <td className="py-1.5 text-right tabular-nums">{b.median_holding_hours == null ? '–' : `${b.median_holding_hours.toFixed(1)} h`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      {performance.notes.length ? (
        <ul className="mt-4 space-y-1 text-xs text-amber-700 dark:text-amber-300">
          {performance.notes.map((n) => <li key={n}>{n}</li>)}
        </ul>
      ) : null}
    </Panel>
  );
}

'use client';

import { useState } from 'react';
import classNames from 'classnames';
import { usd } from '@/data/format';
import { pct, pnlTint, stressMatrix, type Stress } from '@/data/portfolio';
import { Panel, PanelState, toneOf } from '@/components/Panel';

/** P&L of the open trades under SPX x IV shocks (heatmap) and on the largest real SPX days. */
export function StressPanel({ stress, status }: { stress: Stress | null; status: 'loading' | 'ready' | 'error' }) {
  const [days, setDays] = useState(0);
  if (status !== 'ready' || !stress) {
    return <Panel eyebrow="What if" title="Stress tests"><PanelState status={status === 'error' ? 'error' : 'loading'} service="The stats service (8084)" /></Panel>;
  }
  if (stress.open_trades === 0) {
    return <Panel eyebrow="What if" title="Stress tests"><p className="text-sm text-slate-500 dark:text-slate-400">No open trades to stress.</p></Panel>;
  }
  const matrix = stressMatrix(stress, days);
  const scale = Math.max(1, ...stress.grid.map((r) => Math.abs(r.pnl)));
  const calls = stress.summary.grid.margin_calls + stress.summary.historical.margin_calls;

  const toggle = (
    <div className="inline-flex rounded-full bg-slate-100 p-1 dark:bg-slate-800">
      {stress.axes.horizons_days.map((d) => (
        <button key={d} onClick={() => setDays(d)} className={classNames('rounded-full px-3 py-1 text-xs', days === d ? 'bg-white shadow dark:bg-slate-700' : 'text-slate-500')}>
          {d === 0 ? 'Right now' : `After ${d} day`}
        </button>
      ))}
    </div>
  );

  return (
    <Panel eyebrow="What if" title="Stress tests" aside={toggle}>
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs tabular-nums">
          <thead className="text-slate-500">
            <tr>
              <th className="py-1 pr-2 text-left font-normal">IV \ SPX</th>
              {stress.axes.spx_moves.map((m) => <th key={m} className="px-1 py-1 text-right font-normal">{pct(m, 0)}</th>)}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row) => (
              <tr key={row.ivShift}>
                <td className="py-1 pr-2 text-slate-500">{row.ivShift >= 0 ? '+' : ''}{row.ivShift} pts</td>
                {row.cells.map((c) => (
                  <td
                    key={c.name}
                    title={`${c.name}: ${usd(c.pnl)}${c.short_of_capital ? ' — short of capital' : ''}`}
                    className={classNames('px-1 py-1.5 text-right', c.short_of_capital && 'outline outline-2 -outline-offset-2 outline-rose-500')}
                    style={{ backgroundColor: pnlTint(c.pnl, scale) }}
                  >
                    {Math.abs(c.pnl) >= 1000 ? `${(c.pnl / 1000).toFixed(1)}k` : c.pnl.toFixed(0)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
        Dollar P&L of the shock alone (0 = no change). Rows shift every option&apos;s implied vol by that many points.
        {calls ? ' Outlined cells leave the account short of capital (a margin call).' : ' No scenario leaves the account short of capital.'}
      </p>

      {stress.historical.length ? (
        <>
          <h3 className="mt-6 text-sm font-semibold">The largest real SPX days, replayed on today&apos;s book</h3>
          <table className="mt-2 min-w-full text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="py-1 pr-3 text-left">Day</th>
                <th className="py-1 pr-3 text-right">SPX</th>
                <th className="py-1 pr-3 text-right">VIX</th>
                <th className="py-1 pr-3 text-right">P&L</th>
                <th className="py-1 text-right">Of account</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-500/20">
              {stress.historical.map((r) => (
                <tr key={r.name} className={r.short_of_capital ? 'text-rose-600 dark:text-rose-400' : ''}>
                  <td className="py-1.5 pr-3">{r.date}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{pct(r.spx_move, 1)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{r.iv_shift >= 0 ? '+' : ''}{r.iv_shift.toFixed(1)}</td>
                  <td className={`py-1.5 pr-3 text-right tabular-nums ${toneOf(r.pnl)}`}>{usd(r.pnl)}</td>
                  <td className="py-1.5 text-right tabular-nums">{pct(r.pct_of_account, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            Each day&apos;s SPX move with its VIX change applied to every option&apos;s IV, one day passing. Weekly options&apos;
            IV usually jumps more than VIX on such days, so the real loss could be larger.
          </p>
        </>
      ) : null}
    </Panel>
  );
}

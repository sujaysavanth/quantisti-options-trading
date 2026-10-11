'use client';

import { usd } from '@/data/format';
import { METHOD_LABELS, pct, type VarHistory, type VarNow } from '@/data/portfolio';
import { Panel, PanelState } from '@/components/Panel';

const ORDER = ['filtered_historical', 'historical', 'delta_gamma_vega'];

/** 1-day VaR and expected shortfall by method, and how the stored VaR has held up against what happened. */
export function VarPanel({ now, history, status }: { now: VarNow | null; history: VarHistory | null; status: 'loading' | 'ready' | 'error' }) {
  if (status !== 'ready' || !now) {
    return <Panel eyebrow="Risk now" title="Value at risk"><PanelState status={status === 'error' ? 'error' : 'loading'} service="The stats service (8084)" /></Panel>;
  }
  const methods = ORDER.filter((m) => now.methods[m]);
  const filtered = now.methods.filtered_historical;
  const tests = (history?.tests ?? []).filter((t) => t.kupiec.observations > 0);

  return (
    <Panel
      eyebrow="Risk now · 1 day"
      title="Value at risk"
      aside="VaR: the loss tomorrow should only exceed 5% / 1% of the time. Expected shortfall: the average loss on those days."
    >
      {now.open_trades === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">No open trades: nothing at risk.</p>
      ) : (
        <table className="min-w-full text-sm">
          <thead className="text-xs uppercase text-slate-500">
            <tr>
              <th className="py-1 pr-3 text-left">Method</th>
              <th className="py-1 pr-3 text-right">VaR 95%</th>
              <th className="py-1 pr-3 text-right">VaR 99%</th>
              <th className="py-1 pr-3 text-right">Shortfall 99%</th>
              <th className="py-1 text-right">99% of account</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-500/20">
            {methods.map((m) => {
              const l95 = now.methods[m].levels['0.95'];
              const l99 = now.methods[m].levels['0.99'];
              return (
                <tr key={m}>
                  <td className="py-1.5 pr-3">{METHOD_LABELS[m] ?? m}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{usd(l95?.var)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums font-semibold">{usd(l99?.var)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{usd(l99?.es)}</td>
                  <td className="py-1.5 text-right tabular-nums">{pct(l99 ? -l99.var / now.account_value : null, 1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {filtered?.sigma_now ? (
        <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
          Today&apos;s volatility for the filtered method: {pct(filtered.sigma_now)} a day
          ({filtered.sigma_source === 'garch' ? 'the GARCH forecast from the ml service' : 'an EWMA estimate; the ml forecast was unavailable'}),
          against {pct(filtered.sigma_long_run ?? null)} on average since 2010.
        </p>
      ) : null}

      <h3 className="mt-6 text-sm font-semibold">Track record</h3>
      {tests.length ? (
        <table className="mt-2 min-w-full text-sm">
          <thead className="text-xs uppercase text-slate-500">
            <tr>
              <th className="py-1 pr-3 text-left">Method</th>
              <th className="py-1 pr-3 text-right">Level</th>
              <th className="py-1 pr-3 text-right">Days</th>
              <th className="py-1 pr-3 text-right">Breaches</th>
              <th className="py-1 pr-3 text-right">Expected</th>
              <th className="py-1 text-right">Kupiec p</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-500/20">
            {tests.map((t) => (
              <tr key={`${t.method}-${t.confidence}`}>
                <td className="py-1.5 pr-3">{METHOD_LABELS[t.method] ?? t.method}</td>
                <td className="py-1.5 pr-3 text-right">{Math.round(t.confidence * 100)}%</td>
                <td className="py-1.5 pr-3 text-right tabular-nums">{t.kupiec.observations}</td>
                <td className="py-1.5 pr-3 text-right tabular-nums">{t.kupiec.breaches}</td>
                <td className="py-1.5 pr-3 text-right tabular-nums">{t.kupiec.expected.toFixed(1)}</td>
                <td className="py-1.5 text-right tabular-nums">{t.kupiec.p_value == null ? '–' : t.kupiec.p_value.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          No outcomes yet. VaR is stored after each close and checked against the next day&apos;s P&L.
        </p>
      )}
      {history?.note ? <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">{history.note}</p> : null}
    </Panel>
  );
}

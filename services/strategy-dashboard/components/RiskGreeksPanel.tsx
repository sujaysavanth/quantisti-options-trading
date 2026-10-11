'use client';

import { expiryLabel } from '@/data/live';
import { usd } from '@/data/format';
import type { Greeks, GreekTotals } from '@/data/portfolio';
import { Panel, PanelState, Stat, toneOf } from '@/components/Panel';

const COLS: { key: keyof GreekTotals; label: string; hint: string }[] = [
  { key: 'delta', label: 'Delta', hint: 'P&L per 1 SPX point' },
  { key: 'delta_1pct', label: 'Delta, 1% move', hint: 'P&L from delta for a 1% SPX move' },
  { key: 'gamma_1pct', label: 'Gamma, 1% move', hint: 'Extra P&L from gamma for a 1% move either way' },
  { key: 'vega', label: 'Vega', hint: 'P&L per 1 volatility point' },
  { key: 'theta', label: 'Theta', hint: 'P&L per calendar day, all else unchanged' },
];

/** Dollar Greeks of the open positions, from the stats service. */
export function RiskGreeksPanel({ greeks, status }: { greeks: Greeks | null; status: 'loading' | 'ready' | 'error' }) {
  if (status !== 'ready' || !greeks) {
    return <Panel eyebrow="Risk now" title="Greeks"><PanelState status={status === 'error' ? 'error' : 'loading'} service="The stats service (8084)" /></Panel>;
  }
  const empty = greeks.positions.length === 0;
  return (
    <Panel
      eyebrow="Risk now"
      title="Greeks"
      aside="In dollars for the whole book, each expiry priced at its option chain's own time (quotes are ~15 min delayed)."
    >
      {empty ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">No open positions.</p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-5">
            {COLS.map((c) => (
              <Stat key={c.key} label={c.label} hint={c.hint} value={usd(greeks.totals[c.key])} tone={toneOf(greeks.totals[c.key])} />
            ))}
          </div>
          {greeks.by_expiry.length > 1 ? (
            <table className="mt-4 min-w-full text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-1 pr-3 text-left">Expiry</th>
                  {COLS.map((c) => <th key={c.key} className="py-1 pr-3 text-right">{c.label}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-500/20">
                {greeks.by_expiry.map((row) => (
                  <tr key={row.expiry}>
                    <td className="py-1.5 pr-3">{expiryLabel(row.expiry)}</td>
                    {COLS.map((c) => <td key={c.key} className="py-1.5 pr-3 text-right tabular-nums">{usd(row[c.key])}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </>
      )}
      {greeks.unpriced.length ? (
        <p className="mt-3 text-xs text-amber-700 dark:text-amber-300">
          Not priced: {greeks.unpriced.map((u) => `${u.strike} ${u.option_type} ${u.expiry} (${u.reason})`).join('; ')}.
        </p>
      ) : null}
    </Panel>
  );
}

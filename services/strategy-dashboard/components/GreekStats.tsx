'use client';

import type { PositionGreeks } from '@/data/greeks';
import { usd } from '@/data/format';

/** The selected strategy's position Greeks (1 lot), from its legs' implied vols. */
export function GreekStats({ greeks, name, legs }: { greeks: PositionGreeks | null; name?: string; legs: number }) {
  if (!greeks) return null;
  const allMissing = legs > 0 && greeks.missing >= legs;
  const cells = [
    { label: 'Delta', value: usd(greeks.delta), hint: 'per 1-point SPX move' },
    { label: 'Gamma', value: greeks.gamma.toFixed(2), hint: 'delta change per point' },
    { label: 'Theta', value: usd(greeks.theta), hint: 'per calendar day' },
    { label: 'Vega', value: usd(greeks.vega), hint: 'per 1 vol point' },
  ];
  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1">Position Greeks · 1 lot</p>
      <h3 className="text-2xl font-semibold mb-4">{name ?? 'Selected strategy'}</h3>
      {allMissing ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">The quotes for these legs carry no implied volatility, so Greeks aren&apos;t shown.</p>
      ) : (
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cells.map((c) => (
            <div key={c.label} className="rounded-2xl bg-slate-50 dark:bg-slate-800/40 p-4">
              <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{c.label}</dt>
              <dd className="text-2xl font-semibold mt-1 tabular-nums">{c.value}</dd>
              <dd className="text-xs text-slate-400">{c.hint}</dd>
            </div>
          ))}
        </dl>
      )}
      <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
        Black-Scholes-Merton with each leg&apos;s implied volatility (delta from the quote where it has one), dollars per lot.
        {greeks.missing > 0 && !allMissing ? ` ${greeks.missing} leg(s) without an implied vol are left out.` : ''}
      </p>
    </section>
  );
}

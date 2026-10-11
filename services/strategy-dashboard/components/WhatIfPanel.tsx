'use client';

import { useEffect, useState } from 'react';
import { usd } from '@/data/format';
import type { StrategyRecommendation } from '@/data/types';
import { postWhatIf, WHAT_IF_LABELS, type WhatIf } from '@/data/portfolio';
import { Panel } from '@/components/Panel';

const changeTone = (change: number | null, higherIsBetter: boolean | null) => {
  if (change == null || higherIsBetter == null || Math.abs(change) < 0.5) return '';
  return (change > 0) === higherIsBetter ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400';
};

/**
 * The selected strategy against the paper portfolio (stats service, POST /v1/risk/what-if): Greeks, VaR and stress
 * before and after, and the capital it would hold. Run on demand: it reprices the book over ~4,000 scenarios twice.
 */
export function WhatIfPanel({ strategy }: { strategy: StrategyRecommendation | null }) {
  const [result, setResult] = useState<WhatIf | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // A different strategy (or a refreshed one) makes the old answer stale.
  const key = strategy ? strategy.name + strategy.legs.map((l) => `${l.action}${l.strike}${l.optionType}${l.expiry}`).join() : '';
  useEffect(() => {
    setResult(null);
    setError(null);
  }, [key]);

  if (!strategy) return null;

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await postWhatIf(strategy.legs.map((l) => ({
        strike: l.strike, option_type: l.optionType, expiry: l.expiry, side: l.action, quantity: l.quantity ?? 1,
      }))));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The stats service (8084) didn’t answer.');
    } finally {
      setBusy(false);
    }
  };

  const cap = result?.capital;
  return (
    <Panel
      eyebrow="Before you trade"
      title="Against your portfolio"
      aside={
        <button
          onClick={run}
          disabled={busy}
          className="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-slate-900"
        >
          {busy ? 'Checking…' : result ? 'Check again' : 'Check against my portfolio'}
        </button>
      }
    >
      {error ? <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p> : null}
      {!result && !error ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          How {strategy.name} (1 lot, at the mids) would change your open paper positions&apos; Greeks, 1-day VaR and
          worst stress loss, and whether the account has the capital for it.
        </p>
      ) : null}
      {result && cap ? (
        <>
          <p className={`mb-4 text-sm ${cap.fits === false ? 'text-rose-600 dark:text-rose-400' : 'text-slate-600 dark:text-slate-300'}`}>
            {cap.required == null
              ? 'Capital check unavailable (the simulator didn’t answer).'
              : `Holds ${usd(cap.required)} (${cap.basis}) of the ${usd(cap.available_now)} available` +
                (cap.fits ? `, leaving ${usd(cap.available_after)}.` : ': the paper account would refuse this order.')}
            {result.open_trades === 0 ? ' You have no open trades, so "before" is an empty book.' : ''}
          </p>
          <table className="min-w-full text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="py-1 pr-3 text-left">Measure</th>
                <th className="py-1 pr-3 text-right">Now</th>
                <th className="py-1 pr-3 text-right">With this trade</th>
                <th className="py-1 text-right">Change</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-500/20">
              {result.metrics.map((m) => {
                const meta = WHAT_IF_LABELS[m.metric] ?? { label: m.metric, higherIsBetter: null };
                return (
                  <tr key={m.metric}>
                    <td className="py-1.5 pr-3">{meta.label}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{m.before == null ? '–' : usd(m.before)}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{m.after == null ? '–' : usd(m.after)}</td>
                    <td className={`py-1.5 text-right tabular-nums ${changeTone(m.change, meta.higherIsBetter)}`}>
                      {m.change == null ? '–' : `${m.change >= 0 ? '+' : ''}${usd(m.change)}`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
            VaR is the filtered historical method; stress losses are the worst of the SPX × IV grid and of the largest real
            SPX days, as on the Portfolio page.
            {result.candidate.some((l) => l.price_source === 'model') ? ' Legs without a two-sided quote are priced by the model.' : ''}
          </p>
        </>
      ) : null}
    </Panel>
  );
}

'use client';

import { TrendingUp } from 'lucide-react';
import { regimeOf, type ChainSentiment, type LatestFeatures, type VixNow } from '@/data/forecast';
import { expiryLabel } from '@/data/live';

interface Props {
  vix: VixNow | null;
  features: LatestFeatures | null;
  sentiment: ChainSentiment | null;
}

const BASIS: Record<string, string> = { oi: 'open interest', volume: 'volume', model: 'model (synthetic chain)' };

/** VIX, its term structure, the put/call ratio and the regime: all from live or stored data, nothing made up. */
export function MarketContext({ vix, features, sentiment }: Props) {
  const regime = vix ? regimeOf(vix.value) : null;
  const ratio9d = features?.model_features.vix9d_ratio ?? null;
  const term = features?.model_features.vix_term ?? null;
  const inverted = term != null && term > 1;
  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Market regime</p>
          <h2 className="text-2xl font-semibold capitalize">{regime?.label ?? '–'}</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">{regime?.description ?? 'Waiting for VIX'}</p>
        </div>
        <div className="h-12 w-12 shrink-0 rounded-2xl bg-secondary-100 dark:bg-secondary-900/40 flex items-center justify-center text-secondary-600 dark:text-secondary-200">
          <TrendingUp className="h-6 w-6" />
        </div>
      </div>
      <dl className="grid grid-cols-3 gap-3">
        <div className="rounded-2xl bg-slate-50 dark:bg-slate-800/40 p-3">
          <dt className="text-xs text-slate-500 dark:text-slate-400">VIX</dt>
          <dd className="text-2xl font-semibold tabular-nums">{vix ? vix.value.toFixed(1) : '–'}</dd>
          <dd className="text-xs text-slate-400">{vix ? (vix.source === 'intraday' ? 'latest 5-min bar' : `close ${expiryLabel(vix.at)}`) : ''}</dd>
        </div>
        <div className="rounded-2xl bg-slate-50 dark:bg-slate-800/40 p-3">
          <dt className="text-xs text-slate-500 dark:text-slate-400">Term structure</dt>
          <dd className={`text-2xl font-semibold ${inverted ? 'text-rose-500' : ''}`}>{term == null ? '–' : inverted ? 'Inverted' : 'Normal'}</dd>
          <dd className="text-xs text-slate-400 tabular-nums">
            {term == null ? '' : `VIX/VIX3M ${term.toFixed(2)}`}
            {ratio9d == null ? '' : ` · VIX9D/VIX ${ratio9d.toFixed(2)}`}
          </dd>
        </div>
        <div className="rounded-2xl bg-slate-50 dark:bg-slate-800/40 p-3">
          <dt className="text-xs text-slate-500 dark:text-slate-400">Put/call ratio</dt>
          <dd className="text-2xl font-semibold tabular-nums">{sentiment?.pcr != null ? sentiment.pcr.toFixed(2) : '–'}</dd>
          <dd className="text-xs text-slate-400">
            {sentiment?.pcr_basis ? `by ${BASIS[sentiment.pcr_basis] ?? sentiment.pcr_basis}, ${expiryLabel(sentiment.expiry_date)} expiry` : ''}
          </dd>
        </div>
      </dl>
      {features && (
        <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
          Term structure as of the {expiryLabel(features.anchor_date)} close. Inverted (VIX above VIX3M) signals stress.
        </p>
      )}
    </section>
  );
}

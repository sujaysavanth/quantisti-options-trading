'use client';

import { Target } from 'lucide-react';
import type { StrategyRecommendation } from '@/data/types';
import { expiryLabel } from '@/data/live';
import { optionCode, usd } from '@/data/format';

interface Props {
  pick: StrategyRecommendation | null;
  scoredCount: number;
  forecastExpiry: string | null;
  /** When the option quotes behind the pick were taken. */
  asOf?: string | null;
  selectedName?: string;
  onSelect: (s: StrategyRecommendation) => void;
}

/** The forecast's best defined-risk strategy after spread costs, or why there is none. */
const etTime = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit' }) + ' ET';

export function RecommendationCard({ pick, scoredCount, forecastExpiry, asOf, selectedName, onSelect }: Props) {
  const f = pick?.forecast;
  return (
    <section className="rounded-3xl border border-primary-200 dark:border-primary-500/30 bg-primary-50/60 dark:bg-primary-500/5 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-wide text-primary-600 dark:text-primary-300">
            Recommended strategy{asOf ? ` · option prices as of ${etTime(asOf)}` : ''}
          </p>
          {pick && f ? (
            <>
              <h2 className="text-2xl font-semibold">{pick.name}</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {pick.legs.map((l) => `${l.action === 'SELL' ? 'Short' : 'Long'} ${l.strike} ${optionCode(l.optionType)}`).join(' · ')}
                {' · '}expiry {expiryLabel(pick.expiry)}
              </p>
            </>
          ) : (
            <h2 className="text-2xl font-semibold">
              {scoredCount === 0 ? 'No strategies on the forecast expiry' : 'Stand aside this week'}
            </h2>
          )}
        </div>
        <div className="h-12 w-12 shrink-0 rounded-2xl bg-primary-100 dark:bg-primary-900/50 flex items-center justify-center text-primary-600 dark:text-primary-200">
          <Target className="h-6 w-6" />
        </div>
      </div>

      {pick && f ? (
        <>
          <dl className="mt-4 grid gap-3 sm:grid-cols-4">
            {[
              { label: 'Expected P&L after costs', value: usd(f.netExpectedPl) },
              { label: 'Return on risk', value: `${((f.returnOnRisk ?? 0) * 100).toFixed(1)}%` },
              { label: 'Chance of profit', value: `${Math.round(f.probabilityOfProfit * 100)}%` },
              { label: 'Max loss', value: usd(pick.maxLoss) },
            ].map((c) => (
              <div key={c.label} className="rounded-2xl bg-white dark:bg-slate-900 p-3">
                <dt className="text-xs text-slate-500 dark:text-slate-400">{c.label}</dt>
                <dd className="text-xl font-semibold tabular-nums">{c.value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
            Best expected P&L per dollar at risk among defined-risk strategies, after paying half the bid/ask on every leg
            ({usd(f.spreadCost)}{f.spreadUnknown ? `; ${f.spreadUnknown} leg(s) without a two-sided quote not counted` : ''}). It changes only
            when another strategy is clearly better (by 2+ points of return on risk).
            {selectedName !== pick.name && (
              <button type="button" onClick={() => onSelect(pick)} className="ml-2 font-semibold text-primary-600 hover:underline dark:text-primary-300">
                Show it
              </button>
            )}
          </p>
        </>
      ) : (
        <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
          {scoredCount === 0
            ? forecastExpiry
              ? `The forecast covers the ${expiryLabel(forecastExpiry)} expiry. Pick it in the expiry menu to get a recommendation.`
              : 'A recommendation needs the weekly forecast (ml service).'
            : 'No defined-risk strategy has a positive expected P&L once the bid/ask is paid. Under this forecast, the option prices are fair or better for the seller of every structure here, so the honest recommendation is no trade.'}
        </p>
      )}

      <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
        How much to trust this: the edge comes from where the forecast disagrees with option prices. In testing
        (2014-2020), the at-the-money straddle&apos;s own implied range forecast the week better than GARCH (pinball 0.373 vs
        0.382), so that disagreement is not a proven edge. Prices are ~15-minute-delayed mids. Use it for paper trading.
      </p>
    </section>
  );
}

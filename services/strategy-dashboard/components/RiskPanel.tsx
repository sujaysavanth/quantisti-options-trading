'use client';

import type { StrategyRecommendation } from '@/data/types';
import { num, usd } from '@/data/format';

const money = (value: number | null) => (value === null ? 'Unlimited' : usd(value));

/** Max profit / loss, breakevens and capital at risk, computed from the selected strategy's payoff. */
export function RiskPanel({ strategy }: { strategy: StrategyRecommendation | null }) {
  if (!strategy) return null;
  const definedRisk = strategy.maxLoss !== null;
  const cells = [
    { label: 'Max profit', value: money(strategy.maxProfit) },
    { label: 'Max loss', value: money(strategy.maxLoss) },
    { label: 'Reward / risk', value: strategy.riskReward === null ? '–' : `${strategy.riskReward.toFixed(2)}x` },
    { label: strategy.netPremium >= 0 ? 'Credit received' : 'Debit paid', value: usd(Math.abs(strategy.netPremium)) },
  ];
  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between mb-4">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Risk at expiry · 1 lot</p>
          <h3 className="text-2xl font-semibold">{strategy.name}</h3>
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Breakevens: {strategy.breakevens.length ? strategy.breakevens.map((b) => num(b, 2)).join(' and ') : 'none'}
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-4">
        {cells.map((c) => (
          <div key={c.label} className="rounded-2xl bg-slate-50 dark:bg-slate-800/40 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{c.label}</p>
            <p className="text-2xl font-semibold mt-1 tabular-nums">{c.value}</p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
        {definedRisk
          ? `Defined risk: the most this position can lose is ${usd(strategy.maxLoss)}, which is the capital it ties up.`
          : 'Undefined risk: losses grow without limit beyond a strike; the broker sets the margin, so none is shown here.'}
      </p>
    </section>
  );
}

'use client';

import type { StrategyRecommendation } from '@/data/types';
import { ArrowUpRight } from 'lucide-react';
import classNames from 'classnames';
import { optionCode, usd } from '@/data/format';
import { expiryLabel } from '@/data/live';

interface StrategyTableProps {
  strategies: StrategyRecommendation[];
  selectedStrategy?: string;
  onSelect?: (strategy: StrategyRecommendation) => void;
  forecastExpiry?: string | null;
}

const money = (value: number | null) => (value === null ? 'Unlimited' : usd(value));

export function StrategyTable({ strategies, selectedStrategy, onSelect, forecastExpiry }: StrategyTableProps) {
  const scored = strategies.some((s) => s.forecast);
  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between mb-6">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Live strategies</p>
          <h3 className="text-2xl font-semibold">How each fares under the forecast</h3>
        </div>
        <span className="text-sm text-slate-500 dark:text-slate-400 sm:max-w-sm sm:text-right">
          {scored
            ? 'Probability of profit and expected P&L at expiry under the weekly range forecast (1 lot).'
            : forecastExpiry
              ? `The forecast covers the ${expiryLabel(forecastExpiry)} expiry; choose it to see probabilities.`
              : 'Probabilities appear when the weekly forecast is available.'}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-500 dark:text-slate-400">
            <tr>
              <th className="py-3 pr-4 font-semibold">Strategy</th>
              <th className="py-3 pr-4 font-semibold">Structure</th>
              <th className="py-3 pr-4 font-semibold">Chance of profit</th>
              <th className="py-3 pr-4 font-semibold">Expected P&L</th>
              <th className="py-3 pr-4 font-semibold">Max profit</th>
              <th className="py-3 pr-4 font-semibold">Max loss</th>
              <th className="py-3 pr-4 font-semibold">Reward / risk</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {strategies.map((strategy) => {
              const isActive = selectedStrategy === strategy.name;
              const f = strategy.forecast;
              return (
                <tr
                  key={strategy.name}
                  className={classNames('cursor-pointer transition-colors',
                    isActive ? 'bg-primary-50 dark:bg-primary-500/10' : 'hover:bg-slate-50 dark:hover:bg-slate-800/40')}
                  onClick={() => onSelect?.(strategy)}
                >
                  <td className="py-4 pr-4">
                    <div className="font-semibold flex items-center gap-2">
                      {strategy.name}
                      <ArrowUpRight className="h-4 w-4 text-primary-500" />
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{strategy.type}</p>
                  </td>
                  <td className="py-4 pr-4 text-xs text-slate-500 dark:text-slate-400">
                    {strategy.legs.map((leg) => `${leg.action === 'SELL' ? 'Short' : 'Long'} ${leg.strike} ${optionCode(leg.optionType)}`).join(' · ')}
                  </td>
                  <td className="py-4 pr-4 font-semibold tabular-nums">{f ? `${Math.round(f.probabilityOfProfit * 100)}%` : '–'}</td>
                  <td className={classNames('py-4 pr-4 font-semibold tabular-nums',
                    f ? (f.expectedPl >= 0 ? 'text-emerald-500' : 'text-rose-500') : '')}>
                    {f ? usd(f.expectedPl) : '–'}
                  </td>
                  <td className="py-4 pr-4 tabular-nums">{money(strategy.maxProfit)}</td>
                  <td className="py-4 pr-4 tabular-nums">{money(strategy.maxLoss)}</td>
                  <td className="py-4 pr-4 tabular-nums">{strategy.riskReward === null ? '–' : `${strategy.riskReward.toFixed(2)}x`}</td>
                </tr>
              );
            })}
            {strategies.length === 0 && (
              <tr>
                <td colSpan={7} className="py-6 text-center text-slate-500">No strategies yet: waiting for live option quotes.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {scored && (
        <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
          Expected P&L averages the payoff over the forecast&apos;s distribution of the close, priced at today&apos;s mids. It is an
          estimate, as good as the forecast&apos;s calibration (see its track record above).
        </p>
      )}
    </section>
  );
}

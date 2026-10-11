'use client';

import type { StrategyRecommendation } from '@/data/types';
import { ArrowUpRight } from 'lucide-react';
import classNames from 'classnames';
import { optionCode, usd } from '@/data/format';

interface StrategyTableProps {
  /** Already ranked (data/recommend.ts). */
  strategies: StrategyRecommendation[];
  pickName?: string;
  selectedStrategy?: string;
  onSelect?: (strategy: StrategyRecommendation) => void;
  /** Why nothing is scored on this expiry, if so. */
  reason?: string | null;
}

const money = (value: number | null) => (value === null ? 'Unlimited' : usd(value));

export function StrategyTable({ strategies, pickName, selectedStrategy, onSelect, reason }: StrategyTableProps) {
  const scored = strategies.some((s) => s.forecast);
  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between mb-6">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Live strategies</p>
          <h3 className="text-2xl font-semibold">{scored ? 'Ranked under the forecast' : 'Strategies'}</h3>
        </div>
        <span className="text-sm text-slate-500 dark:text-slate-400 sm:max-w-sm sm:text-right">
          {scored
            ? 'Defined risk by return on risk after spread costs, then undefined risk by expected P&L. 1 lot. Click a row to inspect it.'
            : reason ?? 'Ranking appears when the forecast is available.'}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-500 dark:text-slate-400">
            <tr>
              <th className="py-3 pr-4 font-semibold">Strategy</th>
              <th className="py-3 pr-4 font-semibold">Structure</th>
              <th className="py-3 pr-4 font-semibold">Chance of profit</th>
              <th className="py-3 pr-4 font-semibold">Expected P&L after costs</th>
              <th className="py-3 pr-4 font-semibold">Return on risk</th>
              <th className="py-3 pr-4 font-semibold">Max profit</th>
              <th className="py-3 pr-4 font-semibold">Max loss</th>
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
                      {strategy.name === pickName ? (
                        <span className="rounded-full bg-primary-500 px-2 py-0.5 text-[10px] font-semibold uppercase text-white">Pick</span>
                      ) : (
                        <ArrowUpRight className="h-4 w-4 text-primary-500" />
                      )}
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{strategy.type}</p>
                  </td>
                  <td className="py-4 pr-4 text-xs text-slate-500 dark:text-slate-400">
                    {strategy.legs.map((leg) => `${leg.action === 'SELL' ? 'Short' : 'Long'} ${leg.strike} ${optionCode(leg.optionType)}`).join(' · ')}
                  </td>
                  <td className="py-4 pr-4 font-semibold tabular-nums">{f ? `${Math.round(f.probabilityOfProfit * 100)}%` : '–'}</td>
                  <td className={classNames('py-4 pr-4 font-semibold tabular-nums',
                    f ? (f.netExpectedPl >= 0 ? 'text-emerald-500' : 'text-rose-500') : '')}>
                    {f ? usd(f.netExpectedPl) : '–'}
                  </td>
                  <td className="py-4 pr-4 tabular-nums">
                    {f ? (f.returnOnRisk === null ? 'undefined risk' : `${(f.returnOnRisk * 100).toFixed(1)}%`) : '–'}
                  </td>
                  <td className="py-4 pr-4 tabular-nums">{money(strategy.maxProfit)}</td>
                  <td className="py-4 pr-4 tabular-nums">{money(strategy.maxLoss)}</td>
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
          Expected P&L averages the payoff over the forecast&apos;s distribution of the close at today&apos;s mids, minus half the
          bid/ask on every leg. It is only as good as the forecast&apos;s calibration (track record above).
        </p>
      )}
    </section>
  );
}

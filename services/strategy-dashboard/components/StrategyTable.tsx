'use client';

import type { StrategyRecommendation } from '@/data/mockDashboard';
import { ArrowUpRight } from 'lucide-react';
import classNames from 'classnames';

interface StrategyTableProps {
  strategies: StrategyRecommendation[];
  selectedStrategy?: string;
  onSelect?: (strategy: StrategyRecommendation) => void;
}

const formatCurrency = (value?: number) =>
  `₹${(value ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

export function StrategyTable({ strategies, selectedStrategy, onSelect }: StrategyTableProps) {
  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Strategy Stack</p>
          <h3 className="text-2xl font-semibold">Ranked Opportunities</h3>
        </div>
        <span className="text-sm text-slate-500 dark:text-slate-400">
          Scores combine RR, win probability, and margin efficiency
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-500 dark:text-slate-400">
            <tr>
              <th className="py-3 pr-4 font-semibold">Strategy</th>
              <th className="py-3 pr-4 font-semibold">Type / Strikes</th>
              <th className="py-3 pr-4 font-semibold">Structure</th>
              <th className="py-3 pr-4 font-semibold">Expected P&L</th>
              <th className="py-3 pr-4 font-semibold">Win %</th>
              <th className="py-3 pr-4 font-semibold">R:R</th>
              <th className="py-3 pr-4 font-semibold">Margin</th>
              <th className="py-3 pr-4 font-semibold text-center">Score</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {strategies.map((strategy) => {
              const isActive = selectedStrategy === strategy.name;
              return (
                <tr
                  key={strategy.name}
                  className={classNames(
                    'cursor-pointer transition-colors',
                    isActive
                      ? 'bg-primary-50 dark:bg-primary-500/10'
                      : 'hover:bg-slate-50 dark:hover:bg-slate-800/40'
                  )}
                  onClick={() => onSelect?.(strategy)}
                >
                  <td className="py-4 pr-4">
                    <div className="font-semibold flex items-center gap-2">
                      {strategy.name}
                      <ArrowUpRight className="h-4 w-4 text-primary-500" />
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Max loss {formatCurrency(strategy.maxLoss)}
                    </p>
                  </td>
                  <td className="py-4 pr-4">
                    <p className="text-sm font-medium">{strategy.type}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{strategy.strikes}</p>
                  </td>
                  <td className="py-4 pr-4 text-xs text-slate-500 dark:text-slate-400">
                    {strategy.legs
                      .map(
                        (leg) =>
                          `${leg.action === 'SELL' ? 'Short' : 'Long'} ${leg.strike} ${
                            leg.optionType === 'CALL' ? 'CE' : 'PE'
                          }`
                      )
                      .join(' · ')}
                  </td>
                  <td className="py-4 pr-4 font-semibold text-emerald-500">
                    {formatCurrency(strategy.expectedPl)}
                  </td>
                  <td className="py-4 pr-4">
                    {strategy.winProbability ? Math.round(strategy.winProbability * 100) : 0}%
                  </td>
                  <td className="py-4 pr-4">
                    {strategy.riskReward ? strategy.riskReward.toFixed(1) : '—'}
                  </td>
                  <td className="py-4 pr-4">{`₹${((strategy.margin ?? 0) / 1000).toFixed(0)}K`}</td>
                  <td className="py-4 pr-4 text-center">
                    <span
                      className={classNames(
                        'inline-flex items-center justify-center rounded-full px-3 py-1 text-xs font-semibold',
                        strategy.score > 85
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-200'
                          : 'bg-primary-100 text-primary-800 dark:bg-primary-500/10 dark:text-primary-200'
                      )}
                    >
                      {strategy.score}
                    </span>
                  </td>
                </tr>
              );
            })}
            {strategies.length === 0 && (
              <tr>
                <td colSpan={8} className="py-6 text-center text-slate-500">
                  No strategies available. Ensure market data collectors are running.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

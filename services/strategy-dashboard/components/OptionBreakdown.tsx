'use client';

import type { StrategyRecommendation, OptionLeg } from '@/data/mockDashboard';
import classNames from 'classnames';

interface OptionBreakdownProps {
  strategy: StrategyRecommendation | null;
  selectedLeg?: OptionLeg | null;
  onSelectLeg?: (leg: OptionLeg) => void;
}

const formatCurrency = (value?: number) =>
  `₹${(value ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

export function OptionBreakdown({ strategy, selectedLeg, onSelectLeg }: OptionBreakdownProps) {
  if (!strategy) {
    return (
      <section className="rounded-3xl border border-dashed border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-slate-900/60 p-6 text-center text-slate-500 dark:text-slate-400">
        Select a strategy to view option leg decomposition.
      </section>
    );
  }

  const totalMargin = strategy.legs.reduce((sum, leg) => sum + (leg.marginImpact ?? 0), 0);

  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Leg Decomposition</p>
          <h3 className="text-2xl font-semibold">{strategy.name}</h3>
        </div>
        <div className="text-right">
          <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Net Margin Used</p>
          <p className="text-lg font-semibold">{`₹${(totalMargin / 1000).toFixed(0)}K`}</p>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-xs uppercase text-slate-500 dark:text-slate-400">
            <tr>
          <th className="py-3 pr-4 font-semibold">Action</th>
          <th className="py-3 pr-4 font-semibold">Qty</th>
          <th className="py-3 pr-4 font-semibold">Type</th>
          <th className="py-3 pr-4 font-semibold">Strike</th>
          <th className="py-3 pr-4 font-semibold">Expiry</th>
          <th className="py-3 pr-4 font-semibold">Premium</th>
          <th className="py-3 pr-4 font-semibold">Margin Impact</th>
              <th className="py-3 pr-4 font-semibold text-right">Projected P&L</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {strategy.legs.map((leg, idx) => {
              const isSelected =
                selectedLeg?.strike === leg.strike &&
                selectedLeg?.optionType === leg.optionType &&
                selectedLeg?.action === leg.action;
              return (
                <tr
                  key={`${leg.optionType}-${leg.strike}-${idx}`}
                  className={classNames(
                    'cursor-pointer transition-colors',
                    isSelected
                      ? 'bg-primary-50 dark:bg-primary-500/10'
                      : 'hover:bg-slate-50 dark:hover:bg-slate-800/40'
                  )}
                  onClick={() => onSelectLeg?.(leg)}
                >
                  <td className="py-3 pr-4">
                    <span
                      className={classNames(
                        'rounded-full px-3 py-1 text-xs font-semibold',
                        leg.action === 'SELL'
                          ? 'bg-rose-100 text-rose-700 dark:bg-rose-500/10 dark:text-rose-200'
                          : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200'
                      )}
                  >
                      {leg.action}
                    </span>
                  </td>
                  <td className="py-3 pr-4">{leg.quantity ?? 1}</td>
                  <td className="py-3 pr-4">{leg.optionType}</td>
                  <td className="py-3 pr-4">{`₹${leg.strike.toLocaleString('en-IN')}`}</td>
                  <td className="py-3 pr-4">{leg.expiry}</td>
                  <td className="py-3 pr-4">{formatCurrency(leg.premium)}</td>
                  <td className="py-3 pr-4">
                    <span
                      className={classNames(
                        'font-medium',
                        (leg.marginImpact ?? 0) >= 0 ? 'text-amber-600 dark:text-amber-300' : 'text-slate-500 dark:text-slate-400'
                      )}
                    >
                      {formatCurrency(leg.marginImpact)}
                    </span>
                  </td>
                  <td
                    className={classNames(
                      'py-3 pr-4 text-right font-semibold',
                      (leg.projectedPl ?? 0) >= 0 ? 'text-emerald-500' : 'text-rose-500'
                    )}
                  >
                    {formatCurrency(leg.projectedPl)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

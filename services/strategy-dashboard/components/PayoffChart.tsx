'use client';

import { useEffect, useState } from 'react';
import type { OptionLeg, StrategyRecommendation } from '@/data/types';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, ReferenceLine, ReferenceArea } from 'recharts';
import { num, optionCode, usd } from '@/data/format';

const currencyFormatter = (value: number) => usd(value);

export type ForecastBands = { range80: [number, number]; range90: [number, number]; expiry: string };

interface PayoffChartProps {
  strategy: StrategyRecommendation | null;
  leg?: OptionLeg | null;
  /** The weekly forecast's ranges, shaded when they belong to the strategy's expiry. */
  bands?: ForecastBands | null;
  spot?: number | null;
}

export function PayoffChart({ strategy, leg, bands, spot }: PayoffChartProps) {
  const [isClient, setIsClient] = useState(false);
  useEffect(() => setIsClient(true), []);

  const chartData = leg?.payoffPoints ?? strategy?.payoffPoints ?? [];
  const label = leg
    ? `${leg.action === 'SELL' ? 'Short' : 'Long'} ${leg.strike} ${optionCode(leg.optionType)}`
    : strategy?.name ?? 'Select a strategy';
  const showBands = !!bands && !!strategy && bands.expiry === strategy.expiry;

  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Payoff at expiry · 1 lot</p>
          <h3 className="text-2xl font-semibold">{label}</h3>
        </div>
        <div className="text-right text-xs text-slate-500 dark:text-slate-400 max-w-xs">
          {showBands ? (
            <p>
              Shaded: the forecast&apos;s 80% range (darker) and 90% range for this expiry, re-centred on the live price for the time left.
            </p>
          ) : bands && strategy ? (
            <p>The weekly forecast covers the {bands.expiry} expiry; pick it to see the range here.</p>
          ) : null}
        </div>
      </div>
      <div className="h-72">
        {isClient && chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="payoff" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="price" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(v) => num(v)} stroke="#94a3b8" />
              <YAxis tickFormatter={currencyFormatter} stroke="#94a3b8" />
              <Tooltip
                formatter={(value: number) => currencyFormatter(value)}
                labelFormatter={(l) => `SPX ${num(l)}`}
                contentStyle={{ backgroundColor: '#0f172a', borderRadius: '1rem', border: '1px solid #1e293b', color: '#f8fafc' }}
              />
              {showBands && (
                <ReferenceArea x1={bands!.range90[0]} x2={bands!.range90[1]} ifOverflow="hidden" fill="#6366f1" fillOpacity={0.08} />
              )}
              {showBands && (
                <ReferenceArea x1={bands!.range80[0]} x2={bands!.range80[1]} ifOverflow="hidden" fill="#6366f1" fillOpacity={0.14} />
              )}
              <ReferenceLine y={0} stroke="#e2e8f0" strokeDasharray="4 4" />
              {spot ? <ReferenceLine x={spot} stroke="#94a3b8" strokeDasharray="2 4" label={{ value: 'spot', fill: '#94a3b8', fontSize: 11 }} /> : null}
              <Area type="monotone" dataKey="pl" stroke="#10b981" strokeWidth={3} fillOpacity={1} fill="url(#payoff)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : isClient ? (
          <div className="h-full w-full rounded-2xl bg-slate-100 dark:bg-slate-800/40 flex items-center justify-center text-slate-500 dark:text-slate-400">
            Select a strategy to view its payoff
          </div>
        ) : (
          <div className="h-full w-full rounded-2xl bg-slate-100 dark:bg-slate-800/40 animate-pulse" />
        )}
      </div>
    </section>
  );
}

'use client';

import { useEffect, useState } from 'react';
import type { StrategyRecommendation } from '@/data/mockDashboard';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, ReferenceLine } from 'recharts';

const currencyFormatter = (value: number) => `₹${value.toLocaleString('en-IN')}`;

interface PayoffChartProps {
  strategy: StrategyRecommendation | null;
  leg?: StrategyRecommendation['legs'][number] | null;
}

export function PayoffChart({ strategy, leg }: PayoffChartProps) {
  const [isClient, setIsClient] = useState(false);
  const [updatedAt, setUpdatedAt] = useState('');

  useEffect(() => {
    setIsClient(true);
    setUpdatedAt(new Date().toLocaleString());
  }, []);

  const chartData = leg?.payoffPoints ?? strategy?.payoffPoints ?? [];
  const label = leg
    ? `${leg.action === 'SELL' ? 'Short' : 'Long'} ${leg.strike} ${leg.optionType === 'CALL' ? 'CE' : 'PE'}`
    : strategy?.name ?? 'Select a strategy';

  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Payoff Simulation</p>
          <h3 className="text-2xl font-semibold">{label} Payoff</h3>
        </div>
        <div className="text-right text-sm text-slate-500 dark:text-slate-400">
          <p>{leg ? 'Leg-level projection' : 'Future Greeks adjusted for predicted IV path'}</p>
          {updatedAt && (
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Updated: {updatedAt}
            </p>
          )}
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
              <XAxis
                dataKey="price"
                tickFormatter={(value) => value.toLocaleString('en-IN')}
                stroke="#94a3b8"
              />
              <YAxis
                tickFormatter={currencyFormatter}
                stroke="#94a3b8"
              />
              <Tooltip
                formatter={(value: number) => currencyFormatter(value)}
                labelFormatter={(label) => `Price: ₹${label.toLocaleString('en-IN')}`}
                contentStyle={{
                  backgroundColor: '#0f172a',
                  borderRadius: '1rem',
                  border: '1px solid #1e293b',
                  color: '#f8fafc'
                }}
              />
              <ReferenceLine y={0} stroke="#e2e8f0" strokeDasharray="4 4" />
              <Area
                type="monotone"
                dataKey="pl"
                stroke="#10b981"
                strokeWidth={3}
                fillOpacity={1}
                fill="url(#payoff)"
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : isClient ? (
          <div className="h-full w-full rounded-2xl bg-slate-100 dark:bg-slate-800/40 flex items-center justify-center text-slate-500 dark:text-slate-400">
            Select a strategy to view payoff projection
          </div>
        ) : (
          <div className="h-full w-full rounded-2xl bg-slate-100 dark:bg-slate-800/40 animate-pulse" />
        )}
      </div>
    </section>
  );
}

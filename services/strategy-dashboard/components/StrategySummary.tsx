import { Activity, TrendingUp } from 'lucide-react';

interface SummaryProps {
  weekOf: string;
  expiry: string;
  predictedRange: { lower: number; upper: number; confidence: number };
  closingPriceEstimate: number;
  context: {
    vix: number;
    oiPcr: number;
    trend: string;
  };
}

export function StrategySummary({
  weekOf,
  expiry,
  predictedRange,
  closingPriceEstimate,
  context
}: SummaryProps) {
  return (
    <section className="grid gap-6 md:grid-cols-2">
      <div className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Week Of</p>
            <h2 className="text-2xl font-semibold">{weekOf}</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">Expiry: {expiry}</p>
          </div>
          <div className="h-12 w-12 rounded-2xl bg-primary-100 dark:bg-primary-900/50 flex items-center justify-center text-primary-600 dark:text-primary-200">
            <Activity className="h-6 w-6" />
          </div>
        </div>
        <div className="space-y-2">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Predicted Close Range ({predictedRange.confidence}% confidence)
          </p>
          <div className="text-3xl font-bold">
            {predictedRange.lower.toLocaleString()} – {predictedRange.upper.toLocaleString()}
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">Midpoint: {closingPriceEstimate.toLocaleString()}</p>
        </div>
      </div>
      <div className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Market Regime</p>
            <h2 className="text-2xl font-semibold">{context.trend}</h2>
          </div>
          <div className="h-12 w-12 rounded-2xl bg-secondary-100 dark:bg-secondary-900/40 flex items-center justify-center text-secondary-600 dark:text-secondary-200">
            <TrendingUp className="h-6 w-6" />
          </div>
        </div>
        <dl className="grid grid-cols-2 gap-4">
          <div className="rounded-2xl bg-slate-50 dark:bg-slate-800/40 p-4">
            <dt className="text-sm text-slate-500 dark:text-slate-400">India VIX</dt>
            <dd className="text-2xl font-semibold">{context.vix.toFixed(1)}</dd>
          </div>
          <div className="rounded-2xl bg-slate-50 dark:bg-slate-800/40 p-4">
            <dt className="text-sm text-slate-500 dark:text-slate-400">OI PCR</dt>
            <dd className="text-2xl font-semibold">{context.oiPcr.toFixed(2)}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}

import { dashboardMock } from '@/data/mockDashboard';

export function MarginInsights() {
  const best = dashboardMock.strategies[0];
  const avgMargin =
    dashboardMock.strategies.reduce((sum, strategy) => sum + strategy.margin, 0) /
    dashboardMock.strategies.length;

  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Capital Plan</p>
          <h3 className="text-2xl font-semibold">Margin & Risk Snapshot</h3>
        </div>
        <span className="inline-flex items-center rounded-full bg-primary-100 dark:bg-primary-500/10 px-4 py-1 text-sm font-semibold text-primary-600 dark:text-primary-200">
          Recommended: {best.name}
        </span>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl bg-slate-50 dark:bg-slate-800/40 p-4">
          <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Avg Margin</p>
          <p className="text-3xl font-semibold mt-1">₹{(avgMargin / 1000).toFixed(0)}K</p>
        </div>
        <div className="rounded-2xl bg-slate-50 dark:bg-slate-800/40 p-4">
          <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Best RR</p>
          <p className="text-3xl font-semibold mt-1">{best.riskReward.toFixed(1)}x</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Win Prob {Math.round(best.winProbability * 100)}%</p>
        </div>
        <div className="rounded-2xl bg-slate-50 dark:bg-slate-800/40 p-4">
          <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Expected Net</p>
          <p className="text-3xl font-semibold mt-1">₹{best.expectedPl.toLocaleString('en-IN')}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Score {best.score}</p>
        </div>
      </div>
    </section>
  );
}

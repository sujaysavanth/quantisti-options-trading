import { dashboardMock } from '@/data/mockDashboard';

export function GreekStats() {
  const entries = Object.entries(dashboardMock.greeks);
  const labels: Record<string, string> = {
    delta: 'Delta',
    gamma: 'Gamma',
    theta: 'Theta (₹/day)',
    vega: 'Vega',
    rho: 'Rho'
  };

  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">Future Greeks</p>
      <h3 className="text-2xl font-semibold mb-6">Projected Sensitivities</h3>
      <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {entries.map(([key, value]) => (
          <div key={key} className="rounded-2xl bg-slate-50 dark:bg-slate-800/40 p-4">
            <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{labels[key]}</dt>
            <dd className="text-2xl font-semibold mt-2">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

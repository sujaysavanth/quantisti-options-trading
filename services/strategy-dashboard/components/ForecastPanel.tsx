'use client';

import { Activity, AlertTriangle, CheckCircle2 } from 'lucide-react';
import type { ExpiryForecasts, ForecastBlock, Monitoring, WeeklyForecast } from '@/data/forecast';
import { expiryLabel } from '@/data/live';
import { num } from '@/data/format';

const METHOD_LABELS: Record<string, string> = {
  garch: 'GARCH(1,1), calibrated',
  gbm_sigma: 'Gradient-boosted volatility model',
  vix_raw: 'VIX as published',
};

const range = (r: [number, number]) => `${num(r[0])} – ${num(r[1])}`;

function Alternative({ title, block }: { title: string; block?: ForecastBlock }) {
  if (!block) return null;
  return (
    <div className="flex items-baseline justify-between gap-4 text-sm">
      <span className="text-slate-500 dark:text-slate-400">{title}</span>
      <span className="font-medium tabular-nums">{range(block.range_80)}</span>
    </div>
  );
}

interface Props {
  forecast: WeeklyForecast | null;
  monitoring: Monitoring | null;
  status: 'loading' | 'ready' | 'unavailable';
  expiries?: ExpiryForecasts | null;
}

/** Next week's closing range from the ml service, with its track record. */
export function ForecastPanel({ forecast, monitoring, status, expiries }: Props) {
  if (status !== 'ready' || !forecast) {
    return (
      <section className="rounded-3xl border border-dashed border-slate-300 dark:border-slate-700 bg-white/60 dark:bg-slate-900/60 p-6">
        <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Weekly range forecast</p>
        <h2 className="mt-1 text-2xl font-semibold">{status === 'loading' ? 'Loading…' : 'Forecast unavailable'}</h2>
        {status === 'unavailable' && (
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            The ml service (port 8085) didn&apos;t answer. Strategies below still work; probabilities need the forecast.
          </p>
        )}
      </section>
    );
  }

  const served = forecast.served;
  const track = monitoring?.methods[served.method]?.windows?.last_52_weeks;
  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Next week&apos;s close</p>
          <h2 className="text-2xl font-semibold">Expiry {expiryLabel(forecast.expiry_date)}</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Made at the {expiryLabel(forecast.anchor_date)} close (SPX {num(forecast.spot, 2)}) ·{' '}
            {METHOD_LABELS[served.method] ?? served.method}
          </p>
        </div>
        <div className="h-12 w-12 shrink-0 rounded-2xl bg-primary-100 dark:bg-primary-900/50 flex items-center justify-center text-primary-600 dark:text-primary-200">
          <Activity className="h-6 w-6" />
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <div className="sm:col-span-2">
          <p className="text-sm text-slate-500 dark:text-slate-400">80% likely range</p>
          <p className="text-3xl font-bold tabular-nums">{range(served.range_80)}</p>
          <p className="text-sm text-slate-500 dark:text-slate-400 tabular-nums">
            90%: {range(served.range_90)} · median {num(served.median)}
          </p>
        </div>
        {track && (
          <div className="rounded-2xl bg-slate-50 dark:bg-slate-800/40 p-3 text-sm">
            <p className="flex items-center gap-1 font-medium">
              {track.drift ? <AlertTriangle className="h-4 w-4 text-amber-500" /> : <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
              Track record
            </p>
            <p className="text-slate-500 dark:text-slate-400">
              Last {track.weeks} weeks: the close landed inside the 80% range{' '}
              <span className="font-semibold text-slate-700 dark:text-slate-200">{Math.round(track.coverage_80 * 100)}%</span> of the time
              {track.drift ? ' (flagged: off target)' : ''}.
            </p>
          </div>
        )}
      </div>

      {forecast.outcome && (
        <p className="mt-3 text-sm">
          Closed at <span className="font-semibold tabular-nums">{num(forecast.outcome.close, 2)}</span>:{' '}
          {forecast.outcome.inside_served_80 ? 'inside' : 'outside'} the 80% range.
        </p>
      )}

      <div className="mt-4 space-y-1 border-t border-slate-100 dark:border-slate-800 pt-3">
        <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Other views (80% range)</p>
        <Alternative title="Second opinion: volatility model (better in stressed weeks)" block={forecast.second_opinion} />
        <Alternative title="VIX as published (usually too wide)" block={forecast.reference} />
        <p className="pt-1 text-xs text-slate-400 dark:text-slate-500">Why GARCH: {served.details}.</p>
      </div>

      {expiries && expiries.expiries.length > 0 && (
        <div className="mt-4 border-t border-slate-100 dark:border-slate-800 pt-3">
          <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Every expiry, from the {expiryLabel(expiries.origin_date)} close (80% range)
          </p>
          <table className="mt-1 w-full text-sm">
            <tbody>
              {expiries.expiries.map((e) => (
                <tr key={e.expiry_date} title={e.validation.reason}>
                  <td className="py-0.5 text-slate-500 dark:text-slate-400">
                    {expiryLabel(e.expiry_date)} <span className="text-xs">({e.sessions}d)</span>
                  </td>
                  <td className="py-0.5 text-right tabular-nums">{range(e.range_80)}</td>
                  <td className="py-0.5 pl-2 text-right text-xs">
                    {e.validation.valid ? <span className="text-emerald-600 dark:text-emerald-400">validated</span> : <span className="text-amber-600">not shown</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="pt-1 text-xs text-slate-400 dark:text-slate-500">
            GARCH for each horizon; checked 2014-2020 (80% ranges held 80-83% of the time) and once on 2021 on (77-78%).
          </p>
        </div>
      )}
    </section>
  );
}

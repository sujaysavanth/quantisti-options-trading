'use client';

import { Lightbulb } from 'lucide-react';
import type { Explanation, GarchExplanation, ShapFeature, TreeExplanation, WeeklyForecast } from '@/data/forecast';
import { num } from '@/data/format';

const FEATURES: Record<string, string> = {
  vix_close: 'VIX level',
  vix_change_1w: 'VIX change over the week',
  vix_hv_spread: 'VIX minus realised volatility',
  vix_pct_1y: 'VIX percentile over a year',
  vix9d: 'VIX9D (9-day VIX)',
  vix9d_ratio: 'VIX9D / VIX',
  vix_term: 'VIX / VIX3M',
  vvix: 'VVIX (volatility of VIX)',
  atm_iv_1w: 'ATM implied vol, next expiry',
  skew_25d: '25-delta put skew',
  pc_volume_ratio: 'Put/call volume',
};

const GROUPS: Record<string, string> = {
  vix: 'VIX level and change',
  vix_term: 'VIX term structure, vol of vol',
  options: 'Option chain',
};

const pctPts = (sigma: number) => `±${(sigma * 100).toFixed(2)}%`;
const signedPts = (x: number) => `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toFixed(2)}`;

function formatValue(f: ShapFeature): string {
  if (f.value === null) return 'no data';
  if (f.name === 'vix_pct_1y') return `${Math.round(f.value * 100)}%`;
  if (f.name === 'atm_iv_1w') return `${(f.value * 100).toFixed(1)}%`;
  if (['vix9d_ratio', 'vix_term', 'pc_volume_ratio', 'skew_25d'].includes(f.name)) return f.value.toFixed(2);
  return f.value.toFixed(1);
}

/** A bar centred on x1: right for wider, left for narrower; log scale so x2 and x0.5 are the same length. */
function MultiplierBar({ m }: { m: number }) {
  const width = Math.min(Math.abs(Math.log(m)) / Math.log(1.5), 1) * 50;
  const wider = m >= 1;
  return (
    <div className="relative h-2 w-full rounded-full bg-slate-100 dark:bg-slate-800">
      <div className="absolute inset-y-0 left-1/2 w-px bg-slate-300 dark:bg-slate-600" />
      <div
        className={`absolute inset-y-0 rounded-full ${wider ? 'bg-rose-400' : 'bg-emerald-400'}`}
        style={wider ? { left: '50%', width: `${width}%` } : { right: '50%', width: `${width}%` }}
      />
    </div>
  );
}

function Garch({ ex, spot }: { ex: GarchExplanation; spot: number }) {
  const rows = [
    { label: 'Long-run level', value: ex.sigma_parts.long_run, base: true },
    { label: `Recent volatility, carried over`, value: ex.sigma_parts.carried_over },
    { label: `Last session's move (${ex.last_move_pct >= 0 ? '+' : ''}${ex.last_move_pct.toFixed(2)}%)`, value: ex.sigma_parts.last_move },
  ];
  return (
    <div>
      <p className="text-sm font-medium">Served forecast: GARCH(1,1)</p>
      <p className="text-sm text-slate-500 dark:text-slate-400">
        Weekly volatility {pctPts(ex.sigma)} (about ±{num(ex.sigma * spot)} points), built from three parts that add up exactly:
      </p>
      <dl className="mt-2 space-y-1 text-sm">
        {rows.map((r) => (
          <div key={r.label} className="flex justify-between gap-4">
            <dt className="text-slate-500 dark:text-slate-400">{r.label}</dt>
            <dd className={`tabular-nums ${r.base ? 'font-medium' : r.value < 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500'}`}>
              {r.base ? pctPts(r.value) : `${signedPts(r.value)} pts`}
            </dd>
          </div>
        ))}
        <div className="flex justify-between gap-4 border-t border-slate-100 dark:border-slate-800 pt-1 font-semibold">
          <dt>This week</dt>
          <dd className="tabular-nums">{pctPts(ex.sigma)}</dd>
        </div>
      </dl>
      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
        Daily volatility now runs {(ex.daily_vol_now_annual * 100).toFixed(1)}% annualised
        {ex.daily_vol_long_run_annual != null ? ` against a long-run ${(ex.daily_vol_long_run_annual * 100).toFixed(1)}%` : ''}
        {ex.half_life_sessions != null ? `; a shock's effect halves every ${ex.half_life_sessions.toFixed(0)} sessions.` : '.'}
      </p>
    </div>
  );
}

function Tree({ ex, garchSigma }: { ex: TreeExplanation; garchSigma?: number }) {
  const top = ex.groups[0];
  const diff = garchSigma ? ex.sigma / garchSigma - 1 : null;
  return (
    <div>
      <p className="text-sm font-medium">Second opinion: volatility model, explained with SHAP</p>
      <p className="text-sm text-slate-500 dark:text-slate-400">
        {pctPts(ex.sigma)} against {pctPts(ex.sigma_base)} for its average week; each driver multiplies the width.
      </p>
      <ul className="mt-2 space-y-2 text-sm">
        {ex.groups.map((g) => (
          <li key={g.group} className="grid grid-cols-[1fr_6rem_3.5rem] items-center gap-3">
            <span>{GROUPS[g.group] ?? g.group}</span>
            <MultiplierBar m={g.multiplier} />
            <span className="text-right tabular-nums">×{g.multiplier.toFixed(2)}</span>
          </li>
        ))}
      </ul>
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-xs text-slate-500 dark:text-slate-400">Each feature</summary>
        <ul className="mt-2 space-y-1">
          {ex.features.map((f) => (
            <li key={f.name} className="grid grid-cols-[1fr_4.5rem_3.5rem] gap-3 text-xs">
              <span className="text-slate-600 dark:text-slate-300">
                {FEATURES[f.name] ?? f.name}
                {!f.used ? ' (no data in training: not used)' : ''}
              </span>
              <span className="text-right tabular-nums text-slate-500">{formatValue(f)}</span>
              <span className="text-right tabular-nums">×{f.multiplier.toFixed(2)}</span>
            </li>
          ))}
        </ul>
        {ex.features.some((f) => f.used && f.value === null) && (
          <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
            &quot;No data&quot; still moves the forecast: the model learned what weeks without an option chain (2024 to Sep
            2026) looked like, so a missing value is treated as information, not ignored.
          </p>
        )}
      </details>
      {diff != null && top && (
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
          {Math.abs(diff) < 0.02
            ? 'It agrees with GARCH this week.'
            : `It is ${Math.abs(Math.round(diff * 100))}% ${diff < 0 ? 'narrower' : 'wider'} than GARCH; the biggest driver is ${(GROUPS[top.group] ?? top.group).toLowerCase()} (×${top.multiplier.toFixed(2)}).`}
        </p>
      )}
    </div>
  );
}

const isGarch = (e?: Explanation | null): e is GarchExplanation & { added_later?: boolean } => e?.kind === 'garch';
const isTree = (e?: Explanation | null): e is TreeExplanation & { added_later?: boolean } => e?.kind === 'tree_shap';

/** Why next week's range is as wide as it is, for the served forecast and the second opinion. */
export function WhyThisRange({ forecast }: { forecast: WeeklyForecast | null }) {
  const served = forecast?.served.explanation;
  const second = forecast?.second_opinion?.explanation;
  if (!forecast || (!isGarch(served) && !isTree(second))) return null;
  const reference = forecast.reference?.explanation;
  const z = served?.z;
  const factor = z && z.length === 5 ? (z[3] - z[1]) / 2 : null;
  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Why this range</p>
          <h2 className="text-2xl font-semibold">What sets next week&apos;s width</h2>
        </div>
        <div className="h-12 w-12 shrink-0 rounded-2xl bg-amber-100 dark:bg-amber-900/40 flex items-center justify-center text-amber-600 dark:text-amber-200">
          <Lightbulb className="h-6 w-6" />
        </div>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        {isGarch(served) && <Garch ex={served} spot={forecast.spot} />}
        {isTree(second) && <Tree ex={second} garchSigma={isGarch(served) ? served.sigma : undefined} />}
      </div>
      <p className="mt-4 text-xs text-slate-400 dark:text-slate-500">
        {reference?.kind === 'vix' ? `For scale: VIX at ${reference.vix.toFixed(1)} implies ${pctPts(reference.sigma)}. ` : ''}
        These explain the models, not the market: they show why each model gives this width, not why prices move.
        Widths here are the week&apos;s volatility (one standard deviation of its return)
        {factor ? `; the served 80% range spans about ${factor.toFixed(2)} times it on each side of the median` : ''}.
      </p>
    </section>
  );
}

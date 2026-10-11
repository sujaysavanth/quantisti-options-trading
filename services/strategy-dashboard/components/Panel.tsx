import type { ReactNode } from 'react';

/** The card every dashboard section sits in, with an eyebrow, a title and an optional right-hand note. */
export function Panel({ eyebrow, title, aside, children }: { eyebrow: string; title?: ReactNode; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
      <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">{eyebrow}</p>
          {title ? <h2 className="text-2xl font-semibold">{title}</h2> : null}
        </div>
        {aside ? <div className="text-xs text-slate-500 dark:text-slate-400 sm:max-w-sm sm:text-right">{aside}</div> : null}
      </div>
      {children}
    </section>
  );
}

/** What a panel shows while loading or when its service didn't answer. */
export function PanelState({ status, service }: { status: 'loading' | 'error'; service: string }) {
  return (
    <div className="flex h-32 items-center justify-center rounded-2xl bg-slate-100 text-sm text-slate-500 dark:bg-slate-800/40 dark:text-slate-400">
      {status === 'loading' ? 'Loading…' : `${service} didn't answer.`}
    </div>
  );
}

export function Stat({ label, value, tone, hint }: { label: string; value: ReactNode; tone?: string; hint?: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4 dark:bg-slate-800/40" title={hint}>
      <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
      <p className={`mt-1 text-xl font-semibold tabular-nums ${tone ?? ''}`}>{value}</p>
    </div>
  );
}

export const toneOf = (v: number | null | undefined) =>
  v == null ? '' : v > 0 ? 'text-emerald-600 dark:text-emerald-400' : v < 0 ? 'text-rose-600 dark:text-rose-400' : '';

'use client';

import { useCallback, useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { EquityPanel } from '@/components/EquityPanel';
import { RiskGreeksPanel } from '@/components/RiskGreeksPanel';
import { StressPanel } from '@/components/StressPanel';
import { VarPanel } from '@/components/VarPanel';
import {
  fetchEquity, fetchGreeks, fetchPerformance, fetchStress, fetchVar, fetchVarHistory, tradesCsvUrl,
  type Greeks, type Performance, type Snapshot, type Stress, type VarHistory, type VarNow,
} from '@/data/portfolio';

type Status = 'loading' | 'ready' | 'error';
const REFRESH_MS = 60_000;

const settle = <T,>(r: PromiseSettledResult<T>): [T | null, Status] =>
  r.status === 'fulfilled' ? [r.value, 'ready'] : [null, 'error'];

/** The paper portfolio: performance and equity curve (portfolio service), Greeks, stress and VaR (stats service). */
export default function PortfolioPage() {
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [snapshots, setSnapshots] = useState<Record<'close' | 'intraday', Snapshot[] | null>>({ close: null, intraday: null });
  const [greeks, setGreeks] = useState<Greeks | null>(null);
  const [stress, setStress] = useState<Stress | null>(null);
  const [varNow, setVarNow] = useState<VarNow | null>(null);
  const [varHistory, setVarHistory] = useState<VarHistory | null>(null);
  const [status, setStatus] = useState<Record<'equity' | 'greeks' | 'stress' | 'var', Status>>({
    equity: 'loading', greeks: 'loading', stress: 'loading', var: 'loading',
  });
  const [updated, setUpdated] = useState<Date | null>(null);

  const load = useCallback(async () => {
    const [perf, close, intraday, g, s, v, vh] = await Promise.allSettled([
      fetchPerformance(), fetchEquity('close'), fetchEquity('intraday'), fetchGreeks(), fetchStress(), fetchVar(), fetchVarHistory(),
    ]);
    const [p, pStatus] = settle(perf);
    const [gv, gStatus] = settle(g);
    const [sv, sStatus] = settle(s);
    const [vv, vStatus] = settle(v);
    setPerformance(p);
    setSnapshots({ close: settle(close)[0], intraday: settle(intraday)[0] });
    setGreeks(gv);
    setStress(sv);
    setVarNow(vv);
    setVarHistory(settle(vh)[0]);
    setStatus({ equity: pStatus, greeks: gStatus, stress: sStatus, var: vStatus });
    setUpdated(new Date());
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  return (
    <main className="min-h-screen bg-slate-50 py-10 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto max-w-6xl space-y-6 px-4">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Paper portfolio</p>
            <h1 className="text-4xl font-semibold">Portfolio &amp; risk</h1>
            <p className="mt-1 text-slate-500 dark:text-slate-400">
              How the $30,000 paper account has done, and what could happen to the trades still open.
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
            {updated ? <span>Updated {updated.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}</span> : null}
            <a
              href={tradesCsvUrl('all')}
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              <Download className="h-4 w-4" aria-hidden="true" /> Trades CSV
            </a>
          </div>
        </header>

        <EquityPanel performance={performance} snapshots={snapshots} status={status.equity} />
        <div className="grid gap-6 lg:grid-cols-2">
          <RiskGreeksPanel greeks={greeks} status={status.greeks} />
          <VarPanel now={varNow} history={varHistory} status={status.var} />
        </div>
        <StressPanel stress={stress} status={status.stress} />
      </div>
    </main>
  );
}

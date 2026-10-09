'use client';

import { useCallback, useEffect, useState } from 'react';
import classNames from 'classnames';
import { usd } from '@/data/format';
import { expiryLabel } from '@/data/live';
import {
  closeTrade, countdown, deleteTrade, etDateTime, fetchAccount, fetchTrades, type PaperAccount, type PaperTrade,
} from '@/data/paper';

const tone = (v: number) => (v >= 0 ? 'text-emerald-500' : 'text-rose-500');

function AccountBar({ account }: { account: PaperAccount }) {
  const cells = [
    { label: 'Starting balance', value: usd(account.starting_balance) },
    { label: 'Realised P&L', value: usd(account.realised_pnl), cls: tone(account.realised_pnl) },
    { label: 'Unrealised P&L', value: usd(account.unrealised_pnl), cls: tone(account.unrealised_pnl) },
    { label: 'Total P&L', value: usd(account.total_pnl), cls: tone(account.total_pnl), strong: true },
    { label: 'Account value', value: usd(account.account_value), strong: true },
    { label: 'Capital held', value: usd(account.capital_held) },
    { label: 'Available', value: usd(account.available), strong: true },
  ];
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
      {cells.map((c) => (
        <div key={c.label} className="rounded-2xl border border-slate-500/20 bg-slate-500/5 p-3">
          <dt className="text-xs text-slate-500 dark:text-slate-400">{c.label}</dt>
          <dd className={classNames('tabular-nums', c.strong ? 'text-lg font-semibold' : 'font-medium', c.cls)}>{c.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Legs({ trade }: { trade: PaperTrade }) {
  const closed = trade.status === 'closed';
  return (
    <table className="mt-3 min-w-full text-sm">
      <thead className="text-xs uppercase text-slate-500">
        <tr>
          <th className="py-1 pr-3 text-left">Leg</th>
          <th className="py-1 pr-3 text-left">Entry</th>
          <th className="py-1 pr-3 text-left">{closed ? 'Exit' : 'Mid now'}</th>
          <th className="py-1 pr-3 text-right">P&L</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-500/20">
        {trade.legs.map((leg, i) => (
          <tr key={`${trade.id}-${i}`}>
            <td className="py-1 pr-3">
              {leg.side} {leg.quantity} × {leg.strike} {leg.option_type}
              <span className="ml-2 text-xs text-slate-500">{expiryLabel(leg.expiry)}</span>
            </td>
            <td className="py-1 pr-3 tabular-nums">{leg.entry_price != null ? leg.entry_price.toFixed(2) : '–'}</td>
            <td className="py-1 pr-3 tabular-nums">
              {(closed ? leg.exit_price : leg.current_price) != null ? (closed ? leg.exit_price : leg.current_price)!.toFixed(2) : '–'}
            </td>
            <td className={classNames('py-1 pr-3 text-right tabular-nums', tone(leg.pnl))}>{usd(leg.pnl)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** The paper account: balance and P&L, open trades (expiry, auto-settle time, Close now), closed trades. */
export function PaperBook({ refreshKey = 0 }: { refreshKey?: number }) {
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [account, setAccount] = useState<PaperAccount | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [now, setNow] = useState(() => new Date());

  const load = useCallback(async () => {
    try {
      const [t, a] = await Promise.all([fetchTrades(), fetchAccount()]);
      setTrades(t);
      setAccount(a);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Paper account unavailable (simulator on port 8082)');
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 15_000);
    const tick = setInterval(() => setNow(new Date()), 30_000);
    return () => {
      clearInterval(id);
      clearInterval(tick);
    };
  }, [load, refreshKey]);

  const act = async (id: string, action: (id: string) => Promise<unknown>) => {
    setBusy(id);
    try {
      await action(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setBusy(null);
    }
  };

  const open = trades.filter((t) => t.status === 'open');
  const closed = trades.filter((t) => t.status === 'closed');
  return (
    <div className="space-y-6">
      {account && <AccountBar account={account} />}
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Available = starting balance + realised P&L − capital held. Defined-risk trades hold their max loss; uncovered
        short options hold CBOE-style margin. Open trades settle automatically 30 minutes before their expiry&apos;s close
        at the mids (quotes ~15 min delayed).
      </p>
      {error && <p className="text-sm text-rose-500">{error}</p>}

      <div>
        <h4 className="mb-2 text-lg font-semibold">Open trades ({open.length})</h4>
        {open.length === 0 ? (
          <p className="text-sm text-slate-500">No open trades.</p>
        ) : (
          <div className="space-y-3">
            {open.map((t) => {
              const left = t.settles_at ? countdown(t.settles_at, now) : null;
              return (
                <div key={t.id} className="rounded-2xl border border-slate-500/20 bg-slate-500/5 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold">{t.nickname || t.symbol}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        Expiry {t.expiry ? expiryLabel(t.expiry) : '–'}
                        {t.settles_at ? ` · settles ${etDateTime(t.settles_at)}${left ? ` (in ${left})` : ' (settling now)'}` : ''}
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        Opened {new Date(t.created_at).toLocaleString()}
                        {t.capital_held != null ? ` · holds ${usd(t.capital_held)} (${t.capital_basis})` : ''}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <p className={classNames('text-xl font-semibold tabular-nums', tone(t.pnl))}>{usd(t.pnl)}</p>
                      <button type="button" disabled={busy === t.id} onClick={() => act(t.id, closeTrade)}
                        className="rounded-full bg-primary-500 px-4 py-1.5 text-xs font-semibold text-white hover:bg-primary-400 disabled:opacity-50">
                        Close now
                      </button>
                      <button type="button" disabled={busy === t.id} onClick={() => act(t.id, deleteTrade)}
                        className="text-xs text-slate-500 hover:text-rose-500" title="Remove a trade entered by mistake (no P&L recorded)">
                        Delete
                      </button>
                    </div>
                  </div>
                  <Legs trade={t} />
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div>
        <h4 className="mb-2 text-lg font-semibold">Closed trades ({closed.length})</h4>
        {closed.length === 0 ? (
          <p className="text-sm text-slate-500">None yet.</p>
        ) : (
          <div className="space-y-3">
            {closed.map((t) => (
              <div key={t.id} className="rounded-2xl border border-slate-500/20 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{t.nickname || t.symbol}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Expiry {t.expiry ? expiryLabel(t.expiry) : '–'}
                      {t.closed_at ? ` · closed ${etDateTime(t.closed_at)}` : ''}
                    </p>
                    {t.close_reason && <p className="text-xs text-slate-500 dark:text-slate-400">{t.close_reason}</p>}
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-slate-500">Realised</p>
                    <p className={classNames('text-xl font-semibold tabular-nums', tone(t.pnl))}>{usd(t.pnl)}</p>
                  </div>
                </div>
                <Legs trade={t} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

'use client';

import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import classNames from 'classnames';
import { useLiveQuote } from '@/components/LiveQuoteProvider';
import { defaultExpiry, expiryLabel, legMid, pct, quoteExpiries, type LiveLeg } from '@/data/live';

// Strikes shown either side of spot. SPX lists every 5 points near the money.
const RANGES = [10, 20, 40, 0] as const;   // 0 = all

type Row = { strike: number; call?: LiveLeg; put?: LiveLeg };

const price = (v?: number | null) => (v === null || v === undefined || v === 0 ? '–' : v.toFixed(2));
const count = (v?: number | null) => (v === null || v === undefined ? '–' : v.toLocaleString('en-US'));
const delta = (v?: number | null) => (v === null || v === undefined ? '–' : v.toFixed(2).replace(/^(-?)0\./, '$1.'));

export default function ChainPage() {
  const { quote, status } = useLiveQuote();
  const expiries = quoteExpiries(quote);
  const [picked, setPicked] = useState<string | null>(null);
  const [range, setRange] = useState<(typeof RANGES)[number]>(20);
  const spotRow = useRef<HTMLTableRowElement>(null);
  const tableBox = useRef<HTMLDivElement>(null);

  // The picked expiry may settle and drop out of the quote; fall back to the default then.
  const expiry = picked && expiries.some((e) => e.expiry === picked) ? picked : defaultExpiry(quote);
  const summary = expiries.find((e) => e.expiry === expiry);
  const spot = quote?.last_price ?? 0;
  const centre = spot;   // ITM is defined against spot

  const rows = useMemo<Row[]>(() => {
    if (!quote || !expiry) return [];
    const byStrike = new Map<number, Row>();
    for (const leg of quote.legs) {
      if (leg.expiry !== expiry) continue;
      const row = byStrike.get(leg.strike) ?? { strike: leg.strike };
      if (leg.option_type === 'CALL') row.call = leg;
      else row.put = leg;
      byStrike.set(leg.strike, row);
    }
    const all = Array.from(byStrike.values()).sort((a, b) => a.strike - b.strike);
    if (!range) return all;
    const atm = all.reduce((best, r, i) => (Math.abs(r.strike - centre) < Math.abs(all[best].strike - centre) ? i : best), 0);
    return all.slice(Math.max(0, atm - range), atm + range + 1);
  }, [quote, expiry, range, centre]);

  // Expected move to expiry: ~85% of the ATM straddle (a standard rule of thumb).
  const expectedMove = useMemo(() => {
    const atm = rows.reduce<Row | undefined>(
      (best, r) => (!best || Math.abs(r.strike - centre) < Math.abs(best.strike - centre) ? r : best),
      undefined
    );
    const c = legMid(atm?.call);
    const p = legMid(atm?.put);
    return c && p ? 0.85 * (c + p) : null;
  }, [rows, centre]);

  const splitAt = rows.findIndex((r) => r.strike > centre);

  // Centre the spot line in the table when the expiry or range changes (not on every 15s refresh).
  // Scroll only the table box, never the page.
  const hasRows = rows.length > 0;
  useEffect(() => {
    const box = tableBox.current;
    const row = spotRow.current;
    if (box && row) box.scrollTop = row.offsetTop - box.clientHeight / 2;
  }, [expiry, range, hasRows]);

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-100 py-10 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      <div className="mx-auto max-w-6xl space-y-6 px-4">
        <header className="flex flex-col gap-2">
          <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">SPX index options</p>
          <h1 className="text-4xl font-semibold">Option Chain</h1>
          {quote && (
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-600 dark:text-slate-300">
              <span>
                Spot <strong className="tabular-nums text-slate-900 dark:text-white">{spot.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong>
              </span>
              {summary?.forward && (
                <span>
                  Forward <strong className="tabular-nums text-slate-900 dark:text-white">{summary.forward.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong>
                </span>
              )}
              <span>
                ATM IV <strong className="tabular-nums text-slate-900 dark:text-white">{pct(summary?.atm_iv)}</strong>
              </span>
              {expectedMove && (
                <span>
                  Expected move <strong className="tabular-nums text-slate-900 dark:text-white">±{expectedMove.toFixed(0)}</strong>
                </span>
              )}
            </div>
          )}
        </header>

        {status === 'waiting' && (
          <section className="rounded-3xl border border-dashed border-slate-300 bg-white/60 p-10 text-center dark:border-slate-700 dark:bg-slate-900/60">
            <h3 className="text-2xl font-semibold">Waiting for market data</h3>
            <p className="mx-auto mt-2 max-w-xl text-sm text-slate-500 dark:text-slate-400">
              No SPX chain has reached the market-stream service yet. Start the <code>ingest</code> and <code>stream-bridge</code> services.
            </p>
          </section>
        )}

        {quote && expiries.length > 0 && (
          <section className="space-y-4 rounded-3xl border border-slate-200 bg-white p-4 shadow-lg shadow-slate-200/50 dark:border-slate-800 dark:bg-slate-900 dark:shadow-black/30 sm:p-6">
            <div className="flex flex-wrap gap-2" role="tablist" aria-label="Expiry">
              {expiries.map((e) => (
                <button
                  key={e.expiry}
                  type="button"
                  role="tab"
                  aria-selected={e.expiry === expiry}
                  onClick={() => setPicked(e.expiry)}
                  className={classNames(
                    'rounded-xl border px-3 py-1.5 text-left text-sm transition-colors',
                    e.expiry === expiry
                      ? 'border-slate-900 bg-slate-900 text-white dark:border-white dark:bg-white dark:text-slate-900'
                      : 'border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800'
                  )}
                >
                  <span className="font-medium">{expiryLabel(e.expiry)}</span>{' '}
                  <span className="opacity-70">({e.dte}d)</span>
                  {e.atm_iv ? <span className="ml-1 tabular-nums opacity-70">{pct(e.atm_iv)}</span> : null}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
              Strikes
              {RANGES.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRange(r)}
                  className={classNames(
                    'rounded-full px-2.5 py-0.5',
                    r === range ? 'bg-slate-200 text-slate-900 dark:bg-slate-700 dark:text-white' : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                  )}
                >
                  {r ? `±${r}` : 'All'}
                </button>
              ))}
            </div>

            <div ref={tableBox} className="relative max-h-[70vh] overflow-auto rounded-2xl border border-slate-200 dark:border-slate-800">
              <table className="min-w-full text-right text-sm tabular-nums">
                <thead className="sticky top-0 z-10 bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                  <tr>
                    <th colSpan={6} className="px-2 py-1.5 text-center font-semibold tracking-wide">Calls</th>
                    <th className="px-2 py-1.5 text-center" />
                    <th colSpan={6} className="px-2 py-1.5 text-center font-semibold tracking-wide">Puts</th>
                  </tr>
                  <tr className="border-t border-slate-200 dark:border-slate-700">
                    {['Δ', 'IV', 'OI', 'Vol', 'Bid', 'Ask'].map((h) => (
                      <th key={`c-${h}`} className="px-2 py-1.5 font-medium">{h}</th>
                    ))}
                    <th className="px-3 py-1.5 text-center font-medium">Strike</th>
                    {['Bid', 'Ask', 'Vol', 'OI', 'IV', 'Δ'].map((h) => (
                      <th key={`p-${h}`} className="px-2 py-1.5 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => {
                    const callItm = row.strike < centre;
                    const putItm = row.strike > centre;
                    const itm = 'bg-sky-500/[0.08] dark:bg-sky-400/[0.10]';
                    return (
                      <Fragment key={row.strike}>
                        {i === splitAt && (
                          <tr ref={spotRow} aria-label="Spot price">
                            <td colSpan={13} className="border-y border-amber-400/70 bg-amber-50 px-2 py-1 text-center text-xs font-medium text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                              ▸ SPX {spot.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                            </td>
                          </tr>
                        )}
                        <tr className="border-t border-slate-100 dark:border-slate-800/80">
                          <td className={classNames('px-2 py-1', callItm && itm)}>{delta(row.call?.delta)}</td>
                          <td className={classNames('px-2 py-1', callItm && itm)}>{pct(row.call?.iv)}</td>
                          <td className={classNames('px-2 py-1 text-slate-500', callItm && itm)}>{count(row.call?.open_interest)}</td>
                          <td className={classNames('px-2 py-1 text-slate-500', callItm && itm)}>{count(row.call?.volume)}</td>
                          <td className={classNames('px-2 py-1 font-medium', callItm && itm)}>{price(row.call?.bid)}</td>
                          <td className={classNames('px-2 py-1 font-medium', callItm && itm)}>{price(row.call?.ask)}</td>
                          <td className="bg-slate-50 px-3 py-1 text-center font-semibold dark:bg-slate-800/60">{row.strike.toLocaleString('en-US')}</td>
                          <td className={classNames('px-2 py-1 font-medium', putItm && itm)}>{price(row.put?.bid)}</td>
                          <td className={classNames('px-2 py-1 font-medium', putItm && itm)}>{price(row.put?.ask)}</td>
                          <td className={classNames('px-2 py-1 text-slate-500', putItm && itm)}>{count(row.put?.volume)}</td>
                          <td className={classNames('px-2 py-1 text-slate-500', putItm && itm)}>{count(row.put?.open_interest)}</td>
                          <td className={classNames('px-2 py-1', putItm && itm)}>{pct(row.put?.iv)}</td>
                          <td className={classNames('px-2 py-1', putItm && itm)}>{delta(row.put?.delta)}</td>
                        </tr>
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              IV and Δ are recomputed from each bid/ask mid against the forward implied by put-call parity. Shaded cells are in the money.
              OI shows “–” when the source doesn’t report it. Refreshes every 15 seconds.
            </p>
          </section>
        )}
      </div>
    </main>
  );
}

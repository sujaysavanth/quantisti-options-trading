'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLiveQuote } from '@/components/LiveQuoteProvider';
import { defaultExpiry, expiryLabel, pct, quoteExpiries, type LiveLeg } from '@/data/live';
import { ForecastPanel } from '@/components/ForecastPanel';
import { MarketContext } from '@/components/MarketContext';
import { PayoffChart } from '@/components/PayoffChart';
import { GreekStats } from '@/components/GreekStats';
import { RiskPanel } from '@/components/RiskPanel';
import { StrategyTable } from '@/components/StrategyTable';
import { OptionBreakdown } from '@/components/OptionBreakdown';
import type { OptionLeg, StrategyRecommendation } from '@/data/types';
import { optionCode, usd } from '@/data/format';
import { legPl, payoffCurve, payoffStats, strategyPl } from '@/data/payoff';
import { priceAt, rescale, scorePayoff, type QuantileForecast } from '@/data/distribution';
import { positionGreeks } from '@/data/greeks';
import {
  fetchChainSentiment, fetchLatestFeatures, fetchMonitoring, fetchVix, fetchWeekly, fractionLeft,
  type ChainSentiment, type LatestFeatures, type Monitoring, type VixNow, type WeeklyForecast,
} from '@/data/forecast';

const SIM_API = process.env.NEXT_PUBLIC_SIMULATOR_API ?? 'http://localhost:8082';

/** The selected expiry lives in the URL (?expiry=2026-10-09) so a reload or shared link keeps it. */
const readExpiryParam = () =>
  typeof window === 'undefined' ? null : new URLSearchParams(window.location.search).get('expiry');

const writeExpiryParam = (expiry: string | null) => {
  const url = new URL(window.location.href);
  if (expiry) url.searchParams.set('expiry', expiry);
  else url.searchParams.delete('expiry');
  window.history.replaceState(null, '', url);
};

interface PaperTrade {
  id: string;
  symbol: string;
  nickname?: string;
  created_at: string;
  entry_notional: number;
  current_notional: number;
  pnl: number;
  legs: Array<{
    identifier?: string;
    strike: number;
    option_type: string;
    expiry: string;
    quantity: number;
    side: string;
    entry_price?: number;
    current_price?: number;
    pnl: number;
  }>;
}

/** The live quote's leg for a strategy leg: same OCC id, else same strike/type/expiry. */
const quoteLeg = (legs: LiveLeg[], leg: { identifier?: string; strike: number; option_type: string; expiry: string }) =>
  legs.find((q) => leg.identifier && q.identifier === leg.identifier) ??
  legs.find((q) => q.strike === leg.strike && q.option_type === leg.option_type && q.expiry === leg.expiry);

/** A /v1/strategies-live strategy, with metrics from its actual payoff and IV/delta from the live quote. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toStrategy(s: any, quoteLegs: LiveLeg[]): StrategyRecommendation {
  const spot: number = s.spot_price ?? s.legs?.[0]?.strike ?? 0;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const legs: OptionLeg[] = (s.legs ?? []).map((leg: any) => {
    const q = quoteLeg(quoteLegs, leg);
    const optionLeg: OptionLeg = {
      identifier: leg.identifier, action: leg.side, optionType: leg.option_type, strike: leg.strike,
      expiry: leg.expiry, quantity: leg.quantity ?? 1, premium: leg.price ?? 0,
      iv: q?.iv ?? null, delta: q?.delta ?? null, projectedPl: 0, payoffPoints: [],
    };
    optionLeg.projectedPl = Math.round(legPl(optionLeg, spot));
    optionLeg.payoffPoints = payoffCurve([optionLeg], spot);
    return optionLeg;
  });
  const stats = payoffStats(legs);
  return {
    name: s.name, type: s.category, expiry: s.expiry ?? legs[0]?.expiry ?? '',
    strikes: legs.map((l) => `${l.strike} ${optionCode(l.optionType)}`).join(' / '),
    ...stats, payoffPoints: payoffCurve(legs, spot), legs, forecast: null,
  };
}

export default function Page() {
  const [strategies, setStrategies] = useState<StrategyRecommendation[]>([]);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [selectedLeg, setSelectedLeg] = useState<OptionLeg | null>(null);
  const [orders, setOrders] = useState<PaperTrade[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [sendMessage, setSendMessage] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [feedStatus, setFeedStatus] = useState<'loading' | 'live' | 'waiting'>('loading');
  const { quote } = useLiveQuote();
  const expiries = quoteExpiries(quote);
  // null = "whatever the quote's default is"; set when the user picks one (or from ?expiry=).
  const [expiry, setExpiry] = useState<string | null>(null);
  const [expiryReady, setExpiryReady] = useState(false);

  const [forecast, setForecast] = useState<WeeklyForecast | null>(null);
  const [monitoring, setMonitoring] = useState<Monitoring | null>(null);
  const [forecastStatus, setForecastStatus] = useState<'loading' | 'ready' | 'unavailable'>('loading');
  const [features, setFeatures] = useState<LatestFeatures | null>(null);
  const [vix, setVix] = useState<VixNow | null>(null);
  const [sentiment, setSentiment] = useState<ChainSentiment | null>(null);

  useEffect(() => {
    setExpiry(readExpiryParam());
    setExpiryReady(true);
  }, []);

  const handleExpiryChange = (value: string) => {
    const next = value === defaultExpiry(quote) ? null : value;
    setExpiry(next);
    writeExpiryParam(next);
  };

  // The weekly forecast, its track record and the latest weekly features: they change once a week.
  useEffect(() => {
    const load = async () => {
      try {
        const [w, m] = await Promise.all([fetchWeekly(), fetchMonitoring()]);
        setForecast(w);
        setMonitoring(m);
        setForecastStatus('ready');
      } catch (err) {
        console.error('Weekly forecast unavailable', err);
        setForecastStatus('unavailable');
      }
      try {
        const f = await fetchLatestFeatures();
        setFeatures(f);
        setVix(await fetchVix(f));
      } catch (err) {
        console.error('Latest features unavailable', err);
        setVix(await fetchVix(null).catch(() => null));
      }
    };
    load();
    const id = setInterval(load, 5 * 60_000);
    return () => clearInterval(id);
  }, []);

  // Live VIX and the selected expiry's put/call ratio.
  useEffect(() => {
    const load = async () => {
      try {
        setSentiment(await fetchChainSentiment(expiry ?? defaultExpiry(quote)));
      } catch (err) {
        console.error('Chain sentiment unavailable', err);
        setSentiment(null);
      }
      const v = await fetchVix(features).catch(() => null);
      if (v) setVix(v);
    };
    load();
    const id = setInterval(load, 2 * 60_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiry, quote?.default_expiry, features?.anchor_date]);

  const fetchOrders = useCallback(async () => {
    try {
      const response = await fetch(`${SIM_API}/v1/paper/orders`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`Failed to fetch orders: ${response.status}`);
      setOrders((await response.json()) as PaperTrade[]);
    } catch (err) {
      console.error(err);
    }
  }, []);

  // Live strategies from the simulator for the selected expiry.
  useEffect(() => {
    if (!expiryReady) return;
    const loadStrategies = async () => {
      try {
        const query = new URLSearchParams({ symbol: 'SPX' });
        if (expiry) query.set('expiry', expiry);
        const response = await fetch(`${SIM_API}/v1/strategies-live/?${query}`, { cache: 'no-store' });
        if (response.status === 404 && expiry) {
          // The chosen expiry has settled or isn't quoted any more: go back to the default.
          setExpiry(null);
          writeExpiryParam(null);
          return;
        }
        if (!response.ok) {
          setStrategies([]);
          setFeedStatus('waiting');
          return;
        }
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const live = (await response.json()) as any[];
        setFeedStatus(live.length ? 'live' : 'waiting');
        setStrategies(live.map((s) => toStrategy(s, quote?.legs ?? [])));
      } catch (err) {
        console.error('Failed to load live strategies from simulator', err);
        setStrategies([]);
        setFeedStatus('waiting');
      }
    };
    loadStrategies();
    const id = setInterval(loadStrategies, 30000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiry, expiryReady, quote?.quoted_at]);

  useEffect(() => {
    fetchOrders();
    const id = setInterval(fetchOrders, 15000);
    return () => clearInterval(id);
  }, [fetchOrders]);

  // Probability of profit and expected P&L under the forecast, for strategies on the forecast's expiry.
  // The forecast is made at the anchor's close for the whole week; mid-week it is re-centred on the live
  // price and narrowed to the time left (see rescale), so strategies are scored on what can still happen.
  const spot = quote?.last_price ?? null;
  const dist = useMemo<QuantileForecast | null>(() => {
    if (!forecast) return null;
    const base = { spot: forecast.spot, quantiles: forecast.served.quantiles };
    return rescale(base, spot ?? forecast.spot, fractionLeft(forecast.anchor_date, forecast.expiry_date));
  }, [forecast, spot]);

  const scored = useMemo(() => {
    if (!forecast || !dist) return strategies;
    return strategies.map((s) =>
      s.expiry === forecast.expiry_date
        ? { ...s, forecast: { ...scorePayoff(dist, (p) => strategyPl(s.legs, p)), method: forecast.served.method } }
        : s);
  }, [strategies, forecast, dist]);

  const selected = scored.find((s) => s.name === selectedName) ?? scored[0] ?? null;
  const greeks = useMemo(() => (selected && spot ? positionGreeks(selected.legs, spot) : null), [selected, spot]);
  const range = (lo: number, hi: number): [number, number] => [priceAt(dist!, lo), priceAt(dist!, hi)];
  const bands = forecast && dist
    ? { range80: range(0.1, 0.9), range90: range(0.05, 0.95), expiry: forecast.expiry_date }
    : null;

  const handleSelect = (strategy: StrategyRecommendation) => {
    setSelectedName(strategy.name);
    setSelectedLeg(null);
  };

  const handleSendToSimulator = async () => {
    if (!selected) {
      setSendError('Select a strategy first');
      return;
    }
    setIsSending(true);
    setSendError(null);
    setSendMessage(null);
    try {
      const payload = {
        symbol: 'SPX',
        nickname: selected.name,
        legs: selected.legs.map((leg) => ({
          identifier: leg.identifier, strike: leg.strike, option_type: leg.optionType,
          expiry: leg.expiry.slice(0, 10), quantity: 1, side: leg.action,
        })),
      };
      const response = await fetch(`${SIM_API}/v1/paper/orders`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error((await response.text()) || `Simulator responded ${response.status}`);
      setSendMessage('Strategy sent to simulator. View live P&L below or on the Paper console.');
      fetchOrders();
    } catch (err: unknown) {
      console.error(err);
      setSendError(err instanceof Error ? err.message : 'Failed to send strategy to simulator');
    } finally {
      setIsSending(false);
    }
  };

  const handleDeleteOrder = async (id: string) => {
    try {
      const response = await fetch(`${SIM_API}/v1/paper/orders/${id}`, { method: 'DELETE' });
      if (!response.ok) throw new Error(`Failed to delete trade (${response.status})`);
      fetchOrders();
    } catch (err) {
      console.error(err);
      setSendError('Failed to delete trade');
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-100 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 py-12">
      <div className="mx-auto max-w-6xl px-4 space-y-8">
        <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Quantisti Research</p>
            <h1 className="text-4xl font-semibold">Weekly Strategy Intelligence</h1>
            <p className="text-slate-500 dark:text-slate-400 mt-2">
              Next week&apos;s SPX range forecast, applied to live (delayed) option strategies.
            </p>
          </div>
          {expiries.length > 0 && (
            <label className="flex flex-col gap-1 text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Expiry
              <select
                value={expiry ?? defaultExpiry(quote) ?? ''}
                onChange={(e) => handleExpiryChange(e.target.value)}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm normal-case tracking-normal text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              >
                {expiries.map((e) => (
                  <option key={e.expiry} value={e.expiry}>
                    {expiryLabel(e.expiry)} ({e.dte}d){e.atm_iv ? ` · IV ${pct(e.atm_iv)}` : ''}
                    {forecast && e.expiry === forecast.expiry_date ? ' · forecast' : ''}
                  </option>
                ))}
              </select>
            </label>
          )}
        </header>

        <section className="grid gap-6 md:grid-cols-2">
          <ForecastPanel forecast={forecast} monitoring={monitoring} status={forecastStatus} />
          <MarketContext vix={vix} features={features} sentiment={sentiment} />
        </section>

        {feedStatus === 'waiting' ? (
          <section className="rounded-3xl border border-dashed border-slate-300 dark:border-slate-700 bg-white/60 dark:bg-slate-900/60 p-10 text-center">
            <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Live strategies</p>
            <h3 className="mt-2 text-2xl font-semibold">Waiting for market data</h3>
            <p className="mx-auto mt-2 max-w-xl text-sm text-slate-500 dark:text-slate-400">
              No SPX quote has reached the market-stream service yet. Start the <code>ingest</code> and{' '}
              <code>stream-bridge</code> services; this page checks again every 30 seconds.
            </p>
          </section>
        ) : (
          <>
            <PayoffChart strategy={selected} leg={selectedLeg} bands={bands} spot={spot} />
            <OptionBreakdown strategy={selected} selectedLeg={selectedLeg} onSelectLeg={setSelectedLeg} />
            <RiskPanel strategy={selected} />
            <GreekStats greeks={greeks} name={selected?.name} legs={selected?.legs.length ?? 0} />
          </>
        )}

        <StrategyTable
          strategies={scored}
          selectedStrategy={selected?.name}
          onSelect={handleSelect}
          forecastExpiry={forecast?.expiry_date}
        />

        <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Simulator Bridge</p>
              <h3 className="text-2xl font-semibold">Place Dummy Trade</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Sends the selected strategy to the simulator&apos;s paper-trading endpoint.
              </p>
            </div>
            <button
              type="button"
              onClick={handleSendToSimulator}
              disabled={!selected || isSending}
              className="rounded-full bg-primary-500 px-6 py-2 text-sm font-semibold text-white hover:bg-primary-400 disabled:opacity-50"
            >
              {isSending ? 'Sending...' : 'Send to Simulator'}
            </button>
          </div>
          {sendMessage && <p className="mt-3 text-sm text-emerald-500">{sendMessage}</p>}
          {sendError && <p className="mt-3 text-sm text-rose-500">{sendError}</p>}
          <div className="mt-6">
            <h4 className="text-lg font-semibold mb-3">Live Paper Trades</h4>
            {orders.length === 0 ? (
              <p className="text-sm text-slate-500">No trades yet. Submit the strategy to create one.</p>
            ) : (
              <div className="space-y-3">
                {orders.map((order) => (
                  <div key={order.id} className="rounded-2xl border border-slate-200 dark:border-slate-800 p-4 bg-slate-50 dark:bg-slate-800/30">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-semibold">{order.nickname || order.symbol}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Created {new Date(order.created_at).toLocaleString()}</p>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <p className={order.pnl >= 0 ? 'text-emerald-500 font-semibold' : 'text-rose-400 font-semibold'}>{usd(order.pnl)}</p>
                        <button type="button" onClick={() => handleDeleteOrder(order.id)} className="text-xs text-slate-500 hover:text-rose-400">
                          Delete
                        </button>
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                      {order.legs.map((leg, idx) => (
                        <div key={`${order.id}-leg-${idx}`} className="flex justify-between">
                          <span>{leg.side} {leg.quantity} × {leg.strike} {leg.option_type}</span>
                          <span className={leg.pnl >= 0 ? 'text-emerald-500' : 'text-rose-400'}>{usd(leg.pnl)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <footer className="text-center text-xs text-slate-500 dark:text-slate-400 pt-4 border-t border-slate-200 dark:border-slate-800">
          Forecast: ml service (stored weekly at Friday&apos;s close). Quotes: CBOE, ~15 min delayed. VIX and put/call ratio:
          market service. Payoffs and Greeks per 1 lot (x100).
        </footer>
      </div>
    </main>
  );
}

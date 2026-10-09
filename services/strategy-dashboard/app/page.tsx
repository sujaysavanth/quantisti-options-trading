'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useLiveQuote } from '@/components/LiveQuoteProvider';
import { defaultExpiry, expiryLabel, pct, quoteExpiries, type LiveLeg } from '@/data/live';
import { ForecastPanel } from '@/components/ForecastPanel';
import { MarketContext } from '@/components/MarketContext';
import { WhyThisRange } from '@/components/WhyThisRange';
import { PaperBook } from '@/components/PaperBook';
import { errorText } from '@/data/paper';
import { RecommendationCard } from '@/components/RecommendationCard';
import { fitStrategy, rankStrategies, stickyPick } from '@/data/recommend';
import { PayoffChart } from '@/components/PayoffChart';
import { GreekStats } from '@/components/GreekStats';
import { RiskPanel } from '@/components/RiskPanel';
import { StrategyTable } from '@/components/StrategyTable';
import { OptionBreakdown } from '@/components/OptionBreakdown';
import type { OptionLeg, StrategyRecommendation } from '@/data/types';
import { optionCode } from '@/data/format';
import { legPl, payoffCurve, payoffStats } from '@/data/payoff';
import { priceAt, rescale, type QuantileForecast } from '@/data/distribution';
import { positionGreeks } from '@/data/greeks';
import {
  conditionExpiry, fetchChainSentiment, fetchExpiries, fetchLatestFeatures, fetchMonitoring, fetchVix, fetchWeekly, fractionLeft,
  type ChainSentiment, type ExpiryForecasts, type LatestFeatures, type Monitoring, type VixNow, type WeeklyForecast,
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
      halfSpread: q?.bid != null && q?.ask != null && q.ask >= q.bid ? (q.ask - q.bid) / 2 : null,
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
  const [paperRefresh, setPaperRefresh] = useState(0);
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
  const [expiryForecasts, setExpiryForecasts] = useState<ExpiryForecasts | null>(null);
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
        setExpiryForecasts(await fetchExpiries());
      } catch (err) {
        console.error('Expiry forecasts unavailable', err);
        setExpiryForecasts(null);
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

  // Probability of profit and expected P&L for the shown expiry, from its own forecast (GARCH from the latest
  // close, ml /v1/predict/expiries; the weekly forecast is the fallback for its own expiry). Everything is taken
  // at the moment of the option quotes, not now: the chain is ~15 minutes delayed while the index updates every
  // minute, and mixing the two moments makes options look mispriced by however far SPX moved in between. The
  // centre is that expiry's put-call-parity forward; sessions already traded are removed from the variance.
  const spot = quote?.last_price ?? null;
  const shownExpiry = strategies[0]?.expiry ?? expiry ?? defaultExpiry(quote) ?? null;
  const chainSummary = quote?.expiries?.find((e) => e.expiry === shownExpiry);
  const chainCentre = chainSummary?.forward ?? null;
  const chainTime = chainSummary?.quoted_at ?? quote?.quoted_at ?? null;
  const scoring = useMemo(() => {
    const none = (reason: string | null) => ({ dist: null as QuantileForecast | null, intraday: false, reason, basis: null as string | null });
    if (!shownExpiry) return none(null);
    const at = chainTime ? new Date(chainTime) : new Date();
    const centre = chainCentre ?? spot;
    const ef = expiryForecasts?.expiries.find((e) => e.expiry_date === shownExpiry);
    if (ef && centre) {
      const c = conditionExpiry(ef, centre, at);
      return { ...c, basis: `GARCH from the ${expiryLabel(expiryForecasts!.origin_date)} close, ${ef.sessions}-session horizon` };
    }
    if (forecast && shownExpiry === forecast.expiry_date) {
      const base = { spot: forecast.spot, quantiles: forecast.served.quantiles };
      const dist = rescale(base, centre ?? forecast.spot, fractionLeft(forecast.anchor_date, forecast.expiry_date, at));
      return { dist, intraday: false, reason: null, basis: 'the weekly forecast, re-centred for the time left' };
    }
    return none(expiryForecasts
      ? 'No forecast for this expiry: it is more than 10 sessions out.'
      : 'Forecasts are unavailable (ml service on port 8085).');
  }, [shownExpiry, chainCentre, chainTime, spot, expiryForecasts, forecast]);
  const dist = scoring.dist;

  const ranking = useMemo(() => {
    if (!dist) return rankStrategies(strategies);
    return rankStrategies(strategies.map((s) =>
      s.expiry === shownExpiry ? { ...s, forecast: fitStrategy(s, dist, 'garch') } : s));
  }, [strategies, dist, shownExpiry]);
  const { ranked } = ranking;
  // Sticky: a new leader must beat the current pick clearly (stickyPick) before the recommendation changes.
  const lastPick = useRef<string | null>(null);
  const pick = useMemo(() => stickyPick(ranking, lastPick.current), [ranking]);
  useEffect(() => {
    lastPick.current = pick?.name ?? null;
  }, [pick]);

  // The pick is selected until the user chooses another strategy.
  const selected = ranked.find((s) => s.name === selectedName) ?? pick ?? ranked[0] ?? null;
  const greeks = useMemo(() => (selected && spot ? positionGreeks(selected.legs, spot) : null), [selected, spot]);
  const range = (lo: number, hi: number): [number, number] => [priceAt(dist!, lo), priceAt(dist!, hi)];
  const bands = dist && shownExpiry
    ? { range80: range(0.1, 0.9), range90: range(0.05, 0.95), expiry: shownExpiry }
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
      if (!response.ok) throw new Error(await errorText(response));
      setSendMessage('Strategy sent to the paper account. Its P&L, expiry and settle time are below.');
      setPaperRefresh((n) => n + 1);
    } catch (err: unknown) {
      console.error(err);
      setSendError(err instanceof Error ? err.message : 'Failed to send strategy to simulator');
    } finally {
      setIsSending(false);
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
                  </option>
                ))}
              </select>
            </label>
          )}
        </header>

        <section className="grid gap-6 md:grid-cols-2">
          <ForecastPanel forecast={forecast} monitoring={monitoring} status={forecastStatus} expiries={expiryForecasts} />
          <MarketContext vix={vix} features={features} sentiment={sentiment} />
        </section>

        <WhyThisRange forecast={forecast} />

        {feedStatus !== 'waiting' && (
          <>
            <RecommendationCard
              pick={pick}
              asOf={chainTime}
              reason={scoring.reason}
              basis={scoring.basis}
              intraday={scoring.intraday}
              onSelect={handleSelect}
              selectedName={selected?.name}
            />
            <StrategyTable
              strategies={ranked}
              pickName={pick?.name}
              selectedStrategy={selected?.name}
              onSelect={handleSelect}
              reason={scoring.reason}
            />
          </>
        )}

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

        <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg shadow-slate-200/50 dark:shadow-black/30">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm uppercase tracking-wide text-slate-500 dark:text-slate-400">Simulator Bridge</p>
              <h3 className="text-2xl font-semibold">Place Dummy Trade</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Sends the selected strategy (1 lot, at the mids) to the $30,000 paper account.
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
            <PaperBook refreshKey={paperRefresh} />
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

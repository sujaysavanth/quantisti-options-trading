'use client';

import { useCallback, useEffect, useState } from 'react';
import { ThemeToggle } from '@/components/ThemeToggle';
import { StrategySummary } from '@/components/StrategySummary';
import { PayoffChart } from '@/components/PayoffChart';
import { GreekStats } from '@/components/GreekStats';
import { MarginInsights } from '@/components/MarginInsights';
import { StrategyTable } from '@/components/StrategyTable';
import { OptionBreakdown } from '@/components/OptionBreakdown';
import { dashboardMock, type StrategyRecommendation, type OptionLeg } from '@/data/mockDashboard';

const SIM_API = process.env.NEXT_PUBLIC_SIMULATOR_API ?? 'http://localhost:8082';
const STREAM_API = process.env.NEXT_PUBLIC_MARKET_STREAM_API ?? 'http://localhost:8090';
const LOT_SIZE = 75;

type MarketLegQuote = {
  identifier?: string;
  strike: number;
  option_type: 'CALL' | 'PUT';
  expiry: string;
  bid?: number;
  ask?: number;
  last?: number;
  iv?: number;
};

type MarketQuoteSnapshot = {
  symbol: string;
  last_price: number;
  legs: MarketLegQuote[];
};

const getPremium = (leg: MarketLegQuote) =>
  leg.last ?? leg.bid ?? leg.ask ?? 0;

const toOptionLeg = (leg: MarketLegQuote, action: 'BUY' | 'SELL'): OptionLeg => ({
  identifier: leg.identifier,
  action,
  optionType: leg.option_type,
  strike: leg.strike,
  expiry: leg.expiry,
  premium: getPremium(leg),
  projectedPl: 0,
  marginImpact: 0,
  payoffPoints: []
});

const findLeg = (legs: MarketLegQuote[], target: number, direction: 'above' | 'below') => {
  const filtered =
    direction === 'above'
      ? legs.filter((leg) => leg.strike >= target)
      : legs.filter((leg) => leg.strike <= target);
  if (!filtered.length) {
    return undefined;
  }
  return filtered.reduce((prev, curr) =>
    Math.abs(curr.strike - target) < Math.abs(prev.strike - target) ? curr : prev
  );
};

const buildStrategiesFromQuote = (quote: MarketQuoteSnapshot): StrategyRecommendation[] => {
  const legs = quote.legs ?? [];
  if (!legs.length) {
    return [];
  }

  const expiries = Array.from(
    new Set(
      legs
        .map((leg) => leg.expiry)
        .filter(Boolean)
        .sort((a, b) => new Date(a).getTime() - new Date(b).getTime())
    )
  );

  const activeExpiry = expiries[0];
  const expiryLegs = legs.filter((leg) => leg.expiry === activeExpiry);
  const callLegs = expiryLegs
    .filter((leg) => leg.option_type === 'CALL')
    .sort((a, b) => a.strike - b.strike);
  const putLegs = expiryLegs
    .filter((leg) => leg.option_type === 'PUT')
    .sort((a, b) => a.strike - b.strike);

  const strategies: StrategyRecommendation[] = [];
  const price = quote.last_price;

  const shortCall = findLeg(callLegs, price + 100, 'above');
  const longCall = shortCall ? findLeg(callLegs, shortCall.strike + 100, 'above') : undefined;
  const shortPut = findLeg(putLegs, price - 100, 'below');
  const longPut = shortPut ? findLeg(putLegs, shortPut.strike - 100, 'below') : undefined;

  if (shortCall && longCall && shortPut && longPut) {
    const condorLegs = [
      toOptionLeg(shortCall, 'SELL'),
      toOptionLeg(longCall, 'BUY'),
      toOptionLeg(shortPut, 'SELL'),
      toOptionLeg(longPut, 'BUY')
    ];
    const netCredit = condorLegs.reduce(
      (sum, leg) => sum + (leg.action === 'SELL' ? leg.premium : -leg.premium),
      0
    );
    const expectedPl = Math.round(netCredit * LOT_SIZE);
    const wingWidth = Math.min(longCall.strike - shortCall.strike, shortPut.strike - longPut.strike);
    const maxLoss = Math.round(Math.max(wingWidth * LOT_SIZE - expectedPl, 0));
    strategies.push({
      name: 'Live Iron Condor',
      type: 'Neutral Income',
      strikes: `${shortPut.strike} / ${shortCall.strike}`,
      expectedPl,
      maxLoss,
      winProbability: 0.65,
      riskReward: wingWidth > 0 ? (expectedPl / (wingWidth * LOT_SIZE - expectedPl + 1e-6)) : 1.5,
      margin: Math.max(250000, wingWidth * LOT_SIZE * 2),
      score: 88,
      payoffPoints: [],
      legs: condorLegs
    });
  }

  if (shortPut && longPut) {
    const spreadLegs = [toOptionLeg(shortPut, 'SELL'), toOptionLeg(longPut, 'BUY')];
    const netCredit = spreadLegs.reduce(
      (sum, leg) => sum + (leg.action === 'SELL' ? leg.premium : -leg.premium),
      0
    );
    const expectedPl = Math.round(netCredit * LOT_SIZE);
    const strikeDiff = shortPut.strike - longPut.strike;
    const maxLoss = Math.round(Math.max(strikeDiff * LOT_SIZE - expectedPl, 0));
    strategies.push({
      name: 'Live Bull Put Spread',
      type: 'Directional Credit',
      strikes: `${shortPut.strike} / ${longPut.strike}`,
      expectedPl,
      maxLoss,
      winProbability: 0.7,
      riskReward: strikeDiff > 0 ? (expectedPl / (strikeDiff * LOT_SIZE - expectedPl + 1e-6)) : 1.2,
      margin: Math.max(150000, strikeDiff * LOT_SIZE),
      score: 80,
      payoffPoints: [],
      legs: spreadLegs
    });
  }

  if (shortCall && longCall) {
    const spreadLegs = [toOptionLeg(shortCall, 'SELL'), toOptionLeg(longCall, 'BUY')];
    const netCredit = spreadLegs.reduce(
      (sum, leg) => sum + (leg.action === 'SELL' ? leg.premium : -leg.premium),
      0
    );
    const expectedPl = Math.round(netCredit * LOT_SIZE);
    const strikeDiff = longCall.strike - shortCall.strike;
    const maxLoss = Math.round(Math.max(strikeDiff * LOT_SIZE - expectedPl, 0));
    strategies.push({
      name: 'Live Bear Call Spread',
      type: 'Directional Credit',
      strikes: `${shortCall.strike} / ${longCall.strike}`,
      expectedPl,
      maxLoss,
      winProbability: 0.62,
      riskReward: strikeDiff > 0 ? (expectedPl / (strikeDiff * LOT_SIZE - expectedPl + 1e-6)) : 1.1,
      margin: Math.max(150000, strikeDiff * LOT_SIZE),
      score: 76,
      payoffPoints: [],
      legs: spreadLegs
    });
  }

  return strategies.sort((a, b) => b.expectedPl - a.expectedPl);
};

const computeLegPl = (leg: OptionLeg, price: number) => {
  const qty = leg.quantity ?? 1;
  const premium = leg.premium ?? 0;
  const intrinsic =
    leg.optionType === 'CALL' ? Math.max(price - leg.strike, 0) : Math.max(leg.strike - price, 0);
  const raw = intrinsic - premium;
  return raw * LOT_SIZE * (leg.action === 'BUY' ? 1 : -1) * qty;
};

const buildPayoff = (legs: OptionLeg[], spot: number) => {
  if (!legs.length) return [];
  const strikes = legs.map((l) => l.strike);
  const min = Math.min(spot, ...strikes) - 400;
  const max = Math.max(spot, ...strikes) + 400;
  const step = 50;
  const points: Array<{ price: number; pl: number }> = [];
  for (let p = min; p <= max; p += step) {
    const pl = legs.reduce((sum, leg) => sum + computeLegPl(leg, p), 0);
    points.push({ price: Math.round(p), pl: Math.round(pl) });
  }
  return points;
};

const trendMessages = [
  'Range-bound consolidation',
  'Mild uptrend with acceleration',
  'Volatility spike likely',
  'Bearish drift with short-covering risk',
  'Sideways with bullish bias'
];

const generateSummaryFromQuote = (quote: MarketQuoteSnapshot, fallbackExpiry: string) => {
  const midpoint = quote.last_price;
  const randomMove = Math.max(0.01 * midpoint, Math.random() * 0.03 * midpoint);
  const lower = Math.round(midpoint - randomMove);
  const upper = Math.round(midpoint + randomMove);
  const confidence = 60 + Math.round(Math.random() * 30);
  const predictedClose = Math.round(midpoint + (Math.random() - 0.5) * randomMove * 0.5);

  const expiry =
    quote.legs?.[0]?.expiry
      ? new Date(quote.legs[0].expiry).toLocaleDateString('en-IN', {
          day: '2-digit',
          month: 'short',
          year: 'numeric'
        })
      : fallbackExpiry;

  return {
    weekOf: new Date().toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    }),
    expiry,
    predictedRange: {
      lower,
      upper,
      confidence
    },
    closingPriceEstimate: predictedClose,
    context: {
      vix: Number((12 + Math.random() * 5).toFixed(1)),
      oiPcr: Number((0.8 + Math.random() * 0.5).toFixed(2)),
      trend: trendMessages[Math.floor(Math.random() * trendMessages.length)]
    }
  };
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

export default function Page() {
  const [strategies, setStrategies] = useState<StrategyRecommendation[]>([]);
  const [selected, setSelected] = useState<StrategyRecommendation | null>(null);
  const [selectedLeg, setSelectedLeg] = useState<OptionLeg | null>(null);
  const [orders, setOrders] = useState<PaperTrade[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [sendMessage, setSendMessage] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [summary, setSummary] = useState({
    weekOf: dashboardMock.weekOf,
    expiry: dashboardMock.expiry,
    predictedRange: dashboardMock.predictedRange,
    closingPriceEstimate: dashboardMock.closingPriceEstimate,
    context: dashboardMock.context
  });

  const handleSelect = (strategy: StrategyRecommendation) => {
    setSelected(strategy);
    setSelectedLeg(null);
  };

  const handleLegSelect = (leg: OptionLeg) => setSelectedLeg(leg);

  const selectedName = selected?.name;
  const fetchOrders = useCallback(async () => {
    try {
      const response = await fetch(`${SIM_API}/v1/paper/orders`, { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`Failed to fetch orders: ${response.status}`);
      }
      const data = (await response.json()) as PaperTrade[];
      setOrders(data);
    } catch (err) {
      console.error(err);
    }
  }, []);

  // Keep summary in sync with live quote
  useEffect(() => {
    const loadSummary = async () => {
      try {
        const response = await fetch(`${STREAM_API}/v1/quotes/NIFTY`, { cache: 'no-store' });
        if (!response.ok) return;
        const data = (await response.json()) as MarketQuoteSnapshot;
        if (data?.legs?.length) {
          setSummary(generateSummaryFromQuote(data, dashboardMock.expiry));
        }
      } catch (err) {
        console.error('Failed to load live summary', err);
      }
    };
    loadSummary();
    const id = setInterval(loadSummary, 60000);
    return () => clearInterval(id);
  }, []);

  // Fetch live strategies from simulator
  useEffect(() => {
    const loadStrategies = async () => {
      try {
        const response = await fetch(`${SIM_API}/v1/strategies-live?symbol=NIFTY`, { cache: 'no-store' });
        if (!response.ok) {
          setStrategies([]);
          setSelected(null);
          return;
        }
        const liveStrategies = (await response.json()) as any[];
        const mapped: StrategyRecommendation[] = liveStrategies.map((s) => {
          const legs = (s.legs ?? []).map((leg: any) => {
            const premium = leg.price ?? 0;
            return {
              identifier: leg.identifier,
              action: leg.side,
              optionType: leg.option_type,
              strike: leg.strike,
              expiry: leg.expiry,
              quantity: leg.quantity ?? 1,
              premium,
              projectedPl: 0,
              marginImpact: 0,
              payoffPoints: []
            };
          });

          const strikesLabel = legs.map((l) => `${l.strike} ${l.optionType === 'CALL' ? 'CE' : 'PE'}`).join(' / ');
          const spot = s.spot_price ?? legs[0]?.strike ?? 0;
          const payoffPoints = buildPayoff(legs, spot);
          const plValues = payoffPoints.map((p) => p.pl);
          const maxProfit = plValues.length ? Math.max(...plValues) : 0;
          const maxLossAbs = plValues.length ? Math.abs(Math.min(...plValues)) : 0;
          const netPremium = legs.reduce(
            (sum, leg) => sum + (leg.action === 'SELL' ? 1 : -1) * (leg.premium ?? 0) * LOT_SIZE,
            0
          );
          const expectedPl = Math.round(maxProfit || netPremium);
          const maxLoss = s.max_loss !== null && s.max_loss !== undefined
            ? Math.round(Number(s.max_loss) * LOT_SIZE)
            : Math.round(maxLossAbs || Math.abs(netPremium) || 0);
          const riskReward = maxLoss ? expectedPl / (maxLoss || 1) : 1;

          // Per-leg projected P&L at spot and margin attribution
          const totalMargin = s.margin ? Number(s.margin) : maxLoss;
          const totalShortQty = legs.reduce(
            (sum, leg) => sum + (leg.action === 'SELL' ? (leg.quantity ?? 1) : 0),
            0
          );
          legs.forEach((leg) => {
            const qty = leg.quantity ?? 1;
            leg.projectedPl = computeLegPl(leg, spot);
            const marginUnit = totalShortQty ? totalMargin / totalShortQty : totalMargin;
            leg.marginImpact =
              leg.action === 'SELL' ? Math.max(Math.round(marginUnit * qty), 0) : 0;
            leg.payoffPoints = buildPayoff([leg], spot);
          });

          return {
            name: s.name,
            type: s.category,
            strikes: strikesLabel,
            expectedPl,
            maxLoss,
            winProbability: 0.5,
            riskReward,
            margin: totalMargin,
            score: 80,
            payoffPoints,
            legs
          };
        });

        setStrategies(mapped);
        setSelected((current) => {
          if (!mapped.length) return null;
          if (current) {
            const match = mapped.find((s) => s.name === current.name);
            return match ?? mapped[0];
          }
          return mapped[0];
        });
      } catch (err) {
        console.error('Failed to load live strategies from simulator', err);
        setStrategies([]);
        setSelected(null);
      }
    };
    loadStrategies();
    const id = setInterval(loadStrategies, 30000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    fetchOrders();
    const id = setInterval(fetchOrders, 15000);
    return () => clearInterval(id);
  }, [fetchOrders]);

  const toIsoDate = (value: string) => {
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toISOString().slice(0, 10);
    }
    const fallback = new Date(`${value} UTC`);
    if (!Number.isNaN(fallback.getTime())) {
      return fallback.toISOString().slice(0, 10);
    }
    return value;
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
        symbol: 'NIFTY',
        nickname: selected.name,
        legs: selected.legs.map((leg) => ({
          identifier: leg.identifier,
          strike: leg.strike,
          option_type: leg.optionType,
          expiry: toIsoDate(leg.expiry),
          quantity: 1,
          side: leg.action,
        })),
      };
      const response = await fetch(`${SIM_API}/v1/paper/orders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Simulator responded ${response.status}`);
      }
      setSendMessage('Strategy sent to simulator. View live P&L below or on the Paper console.');
      fetchOrders();
    } catch (err: any) {
      console.error(err);
      setSendError(err.message ?? 'Failed to send strategy to simulator');
    } finally {
      setIsSending(false);
    }
  };

  const handleDeleteOrder = async (id: string) => {
    try {
      const response = await fetch(`${SIM_API}/v1/paper/orders/${id}`, { method: 'DELETE' });
      if (!response.ok) {
        throw new Error(`Failed to delete trade (${response.status})`);
      }
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
              Insights generated from ML forecasts of price, volatility, and Greeks for the upcoming expiry.
            </p>
          </div>
          <ThemeToggle />
        </header>

        <StrategySummary
          weekOf={summary.weekOf}
          expiry={summary.expiry}
          predictedRange={summary.predictedRange}
          closingPriceEstimate={summary.closingPriceEstimate}
          context={summary.context}
        />
        <PayoffChart strategy={selected} leg={selectedLeg} />
        <OptionBreakdown
          strategy={selected}
          selectedLeg={selectedLeg}
          onSelectLeg={handleLegSelect}
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
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          Created {new Date(order.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <p className={order.pnl >= 0 ? 'text-emerald-500 font-semibold' : 'text-rose-400 font-semibold'}>
                          ₹{order.pnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </p>
                        <button
                          type="button"
                          onClick={() => handleDeleteOrder(order.id)}
                          className="text-xs text-slate-500 hover:text-rose-400"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                      {order.legs.map((leg, idx) => (
                        <div key={`${order.id}-leg-${idx}`} className="flex justify-between">
                          <span>
                            {leg.side} {leg.quantity} × {leg.strike} {leg.option_type}
                          </span>
                          <span className={leg.pnl >= 0 ? 'text-emerald-500' : 'text-rose-400'}>
                            ₹{leg.pnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
        <GreekStats />
        <MarginInsights />
        <StrategyTable strategies={strategies} selectedStrategy={selectedName} onSelect={handleSelect} />

        <footer className="text-center text-xs text-slate-500 dark:text-slate-400 pt-4 border-t border-slate-200 dark:border-slate-800">
          Data shown is mock output for {dashboardMock.expiry}. Wire this UI to the ML service once the API is available.
        </footer>
      </div>
    </main>
  );
}

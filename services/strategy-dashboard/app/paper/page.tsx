'use client';

import { useEffect, useMemo, useState } from 'react';
import { useLiveQuote } from '@/components/LiveQuoteProvider';
import { defaultExpiry, expiryLabel, legMid, quoteExpiries } from '@/data/live';
import { PaperBook } from '@/components/PaperBook';
import { errorText } from '@/data/paper';

type QuoteMessage = {
  type: string;
  data: {
    symbol: string;
    last_price: number;
  };
};

const SIM_API = process.env.NEXT_PUBLIC_SIMULATOR_API ?? 'http://localhost:8082';
const STREAM_WS = process.env.NEXT_PUBLIC_STREAM_WS ?? 'ws://localhost:8090/ws/quotes';

interface PaperLegForm {
  identifier?: string;
  strike: string;
  option_type: 'CALL' | 'PUT';
  expiry: string;
  quantity: string;
  side: 'BUY' | 'SELL';
}

// Blank strike/expiry are filled from the live quote (ATM strike, default expiry) once it arrives.
const defaultLeg = (strike = '', expiry = ''): PaperLegForm => ({
  strike,
  option_type: 'CALL',
  expiry,
  quantity: '1',
  side: 'SELL',
});

export default function PaperTradingPage() {
  const { quote } = useLiveQuote();
  const expiries = quoteExpiries(quote);
  const atmStrike = quote ? String(Math.round(quote.last_price / 5) * 5) : '';
  const liveExpiry = defaultExpiry(quote) ?? '';
  const [spot, setSpot] = useState<number | null>(null);
  const [paperRefresh, setPaperRefresh] = useState(0);
  const [symbol, setSymbol] = useState('SPX');
  const [nickname, setNickname] = useState('Weekly strategy');
  const [legs, setLegs] = useState<PaperLegForm[]>([defaultLeg()]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ws = new WebSocket(STREAM_WS);
    ws.onmessage = (event) => {
      try {
        const payload: QuoteMessage = JSON.parse(event.data);
        if (payload.type === 'quote' && payload.data?.symbol === symbol) {
          setSpot(payload.data.last_price);
        }
      } catch (err) {
        console.error('Failed to parse websocket payload', err);
      }
    };
    ws.onerror = () => {
      console.warn('Websocket connection error');
    };
    return () => ws.close();
  }, [symbol]);

  const handleLegChange = (index: number, key: keyof PaperLegForm, value: string) => {
    setLegs((prev) => prev.map((leg, idx) => (idx === index ? { ...leg, [key]: value } : leg)));
  };

  useEffect(() => {
    if (!atmStrike || !liveExpiry) return;
    setLegs((prev) => prev.map((leg) => ({ ...leg, strike: leg.strike || atmStrike, expiry: leg.expiry || liveExpiry })));
  }, [atmStrike, liveExpiry]);

  // The live quote for a form leg, so the user sees what it would fill at before submitting.
  const liveLeg = (leg: PaperLegForm) =>
    quote?.legs.find(
      (l) => l.strike === Number(leg.strike) && l.option_type === leg.option_type && l.expiry === leg.expiry
    );

  const handleAddLeg = () => setLegs((prev) => [...prev, defaultLeg(atmStrike, liveExpiry)]);
  const handleRemoveLeg = (index: number) => setLegs((prev) => prev.filter((_, idx) => idx !== index));

  const payloadLegs = useMemo(
    () =>
      legs.map((leg) => ({
        identifier: leg.identifier?.trim() || undefined,
        strike: Number(leg.strike),
        option_type: leg.option_type,
        expiry: leg.expiry,
        quantity: Number(leg.quantity),
        side: leg.side,
      })),
    [legs]
  );

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await fetch(`${SIM_API}/v1/paper/orders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          nickname,
          legs: payloadLegs,
        }),
      });
      if (!response.ok) {
        throw new Error(await errorText(response));
      }
      setNickname('Weekly strategy');
      setLegs([defaultLeg(atmStrike, liveExpiry)]);
      setPaperRefresh((n) => n + 1);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to create trade');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 py-10">
      <div className="mx-auto max-w-6xl px-4 space-y-8">
        <header className="flex flex-col gap-2">
          <p className="text-sm uppercase tracking-wide text-slate-400">Paper Trading</p>
          <h1 className="text-4xl font-semibold">Simulator Console</h1>
          <p className="text-slate-400">
            Live quotes from Market Stream with simulated trades stored in the simulator service.
          </p>
          <div className="text-lg font-semibold text-emerald-400">
            {(spot ?? quote?.last_price) ? `${symbol} ${(spot ?? quote?.last_price ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'Waiting for quotes...'}
          </div>
        </header>

        <section className="rounded-3xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg shadow-black/30">
          <h2 className="text-2xl font-semibold mb-4">Create Dummy Trade</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm text-slate-400">
              Symbol
              <input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2"
              />
            </label>
            <label className="text-sm text-slate-400">
              Nickname
              <input
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2"
              />
            </label>
          </div>
          <div className="mt-6 space-y-4">
            {legs.map((leg, index) => (
              <div
                key={`leg-${index}`}
                className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 grid gap-3 sm:grid-cols-6"
              >
                <label className="text-xs uppercase text-slate-500">
                  Strike
                  <input
                    value={leg.strike}
                    onChange={(e) => handleLegChange(index, 'strike', e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-1"
                  />
                </label>
                <label className="text-xs uppercase text-slate-500">
                  Type
                  <select
                    value={leg.option_type}
                    onChange={(e) => handleLegChange(index, 'option_type', e.target.value as 'CALL' | 'PUT')}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-1"
                  >
                    <option value="CALL">CALL</option>
                    <option value="PUT">PUT</option>
                  </select>
                </label>
                <label className="text-xs uppercase text-slate-500">
                  Expiry
                  {expiries.length ? (
                    <select
                      value={leg.expiry}
                      onChange={(e) => handleLegChange(index, 'expiry', e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-1"
                    >
                      {expiries.map((e) => (
                        <option key={e.expiry} value={e.expiry}>
                          {expiryLabel(e.expiry)} ({e.dte}d)
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="date"
                      value={leg.expiry}
                      onChange={(e) => handleLegChange(index, 'expiry', e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-1"
                    />
                  )}
                </label>
                <label className="text-xs uppercase text-slate-500">
                  Qty
                  <input
                    value={leg.quantity}
                    onChange={(e) => handleLegChange(index, 'quantity', e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-1"
                  />
                </label>
                <label className="text-xs uppercase text-slate-500">
                  Side
                  <select
                    value={leg.side}
                    onChange={(e) => handleLegChange(index, 'side', e.target.value as 'BUY' | 'SELL')}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-1"
                  >
                    <option value="BUY">BUY</option>
                    <option value="SELL">SELL</option>
                  </select>
                </label>
                <div className="flex items-center justify-between">
                  <label className="text-xs uppercase text-slate-500">
                    Identifier
                    <input
                      value={leg.identifier ?? ''}
                      placeholder="Optional"
                      onChange={(e) => handleLegChange(index, 'identifier', e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-1"
                    />
                  </label>
                  {legs.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveLeg(index)}
                      className="text-xs text-rose-400 hover:text-rose-200"
                    >
                      Remove
                    </button>
                  )}
                </div>
                <p className="text-xs tabular-nums text-slate-400 sm:col-span-6">
                  {(() => {
                    const live = liveLeg(leg);
                    if (!live) return quote ? 'No live quote for this strike/expiry; it will be entered at 0.' : 'Waiting for quotes...';
                    const fmt = (v?: number | null) => (v ? v.toFixed(2) : '–');
                    return `${live.identifier} · Bid ${fmt(live.bid)} · Ask ${fmt(live.ask)} · Mid ${fmt(legMid(live))} (fill price)`;
                  })()}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              onClick={handleAddLeg}
              className="rounded-full border border-slate-800 px-4 py-2 text-sm hover:bg-slate-800"
            >
              Add Leg
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="rounded-full bg-primary-500 px-6 py-2 text-sm font-semibold text-white hover:bg-primary-400 disabled:opacity-50"
            >
              {isSubmitting ? 'Submitting...' : 'Create Paper Trade'}
            </button>
            {error && <span className="text-sm text-rose-400">{error}</span>}
          </div>
        </section>

        <section className="rounded-3xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg shadow-black/30">
          <h2 className="mb-4 text-2xl font-semibold">Paper Account</h2>
          <PaperBook refreshKey={paperRefresh} />
        </section>
      </div>
    </main>
  );
}

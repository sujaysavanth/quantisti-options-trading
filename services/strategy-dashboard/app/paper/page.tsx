'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

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

const defaultLeg = (): PaperLegForm => ({
  strike: '19500',
  option_type: 'CALL',
  expiry: new Date().toISOString().slice(0, 10),
  quantity: '1',
  side: 'SELL',
});

export default function PaperTradingPage() {
  const [spot, setSpot] = useState<number | null>(null);
  const [orders, setOrders] = useState<PaperTrade[]>([]);
  const [symbol, setSymbol] = useState('NIFTY');
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
      setError('Failed to load paper trades');
    }
  }, []);

  useEffect(() => {
    fetchOrders();
    const id = setInterval(fetchOrders, 15000);
    return () => clearInterval(id);
  }, [fetchOrders]);

  const handleLegChange = (index: number, key: keyof PaperLegForm, value: string) => {
    setLegs((prev) => prev.map((leg, idx) => (idx === index ? { ...leg, [key]: value } : leg)));
  };

  const handleAddLeg = () => setLegs((prev) => [...prev, defaultLeg()]);
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
        const text = await response.text();
        throw new Error(text || `Failed with status ${response.status}`);
      }
      setNickname('Weekly strategy');
      setLegs([defaultLeg()]);
      fetchOrders();
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
            {spot ? `NIFTY Spot: ₹${spot.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : 'Waiting for quotes...'}
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
                  <input
                    type="date"
                    value={leg.expiry}
                    onChange={(e) => handleLegChange(index, 'expiry', e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-1"
                  />
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
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-semibold">Open Paper Trades</h2>
            <button
              type="button"
              onClick={fetchOrders}
              className="rounded-full border border-slate-700 px-4 py-1 text-sm text-slate-300 hover:bg-slate-800"
            >
              Refresh
            </button>
          </div>
          {orders.length === 0 ? (
            <p className="text-slate-400">No trades yet. Submit one above.</p>
          ) : (
            <div className="space-y-4">
              {orders.map((order) => (
                <div key={order.id} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-lg font-semibold">{order.nickname || order.symbol}</p>
                      <p className="text-xs uppercase text-slate-500">
                        Created {new Date(order.created_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-slate-400">PnL</p>
                      <p className={order.pnl >= 0 ? 'text-emerald-400 text-xl font-semibold' : 'text-rose-400 text-xl font-semibold'}>
                        ₹{order.pnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead className="text-xs uppercase text-slate-500">
                        <tr>
                          <th className="py-2 pr-3">Leg</th>
                          <th className="py-2 pr-3">Entry</th>
                          <th className="py-2 pr-3">Current</th>
                          <th className="py-2 pr-3">PnL</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        {order.legs.map((leg, idx) => (
                          <tr key={`${order.id}-leg-${idx}`}>
                            <td className="py-2 pr-3">
                              <div className="font-semibold">
                                {leg.side} {leg.quantity} × {leg.strike} {leg.option_type}
                              </div>
                              <div className="text-xs text-slate-500">{leg.identifier || leg.expiry}</div>
                            </td>
                            <td className="py-2 pr-3">₹{leg.entry_price?.toLocaleString('en-IN', { maximumFractionDigits: 2 }) ?? '--'}</td>
                            <td className="py-2 pr-3">₹{leg.current_price?.toLocaleString('en-IN', { maximumFractionDigits: 2 }) ?? '--'}</td>
                            <td className={`py-2 pr-3 ${leg.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                              ₹{leg.pnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

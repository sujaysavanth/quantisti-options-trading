/** Clients for the weekly range forecast (ml service) and market context (market service). */

import type { Quantiles } from './distribution';

export const ML_API = process.env.NEXT_PUBLIC_ML_API ?? 'http://localhost:8085';
export const MARKET_API = process.env.NEXT_PUBLIC_MARKET_API ?? 'http://localhost:8081';

export type ForecastBlock = {
  method: string;
  origin: string;
  details: string;
  trained_through: string | null;
  quantiles: Quantiles;
  levels: Quantiles;
  median: number;
  range_80: [number, number];
  range_90: [number, number];
};

export type WeeklyForecast = {
  symbol: string;
  anchor_date: string;
  expiry_date: string;
  spot: number;
  vix_close: number | null;
  served: ForecastBlock;
  second_opinion?: ForecastBlock;
  reference?: ForecastBlock;
  outcome?: { close: number; close_ret: number; inside_served_80: boolean };
};

export type WindowStats = {
  weeks: number;
  coverage_80: number;
  coverage_90: number;
  width_80: number;
  drift: boolean;
  drift_p_value: number;
};

export type Monitoring = {
  methods: Record<string, { role: string; windows: Record<string, WindowStats>; live_weeks: number }>;
  alerts: string[];
};

export type LatestFeatures = { anchor_date: string; model_features: Record<string, number | null> };

export type ChainSentiment = { date: string; expiry_date: string; pcr: number | null; pcr_basis: string | null };

export type VixNow = { value: number; at: string; source: 'intraday' | 'close' };

async function get<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${url} -> ${response.status}`);
  return (await response.json()) as T;
}

export const fetchWeekly = () => get<WeeklyForecast>(`${ML_API}/v1/predict/weekly`);
export const fetchMonitoring = () => get<Monitoring>(`${ML_API}/v1/predict/monitoring`);
export const fetchLatestFeatures = async () =>
  (await get<{ features: LatestFeatures }>(`${ML_API}/v1/features/latest/SPX`)).features;

/** Put/call ratio of the chain for `expiry` (or the default one), strikes within 250 points of spot. */
export async function fetchChainSentiment(expiry?: string | null): Promise<ChainSentiment> {
  const query = new URLSearchParams({ strike_range: '50' });
  if (expiry) query.set('expiry_date', expiry);
  const c = await get<ChainSentiment>(`${MARKET_API}/v1/options/chain?${query}`);
  return { date: c.date, expiry_date: c.expiry_date, pcr: c.pcr, pcr_basis: c.pcr_basis };
}

/** Latest VIX: the newest intraday bar, else the latest weekly feature's close. */
export async function fetchVix(fallback?: LatestFeatures | null): Promise<VixNow | null> {
  try {
    const bars = await get<{ data: { ts: string; close: number }[] }>(
      `${MARKET_API}/v1/underlying/intraday?symbol=VIX&interval=5m`);
    const last = bars.data[bars.data.length - 1];
    if (last) return { value: last.close, at: last.ts, source: 'intraday' };
  } catch {
    // fall through to the weekly close
  }
  const close = fallback?.model_features.vix_close;
  return close != null && fallback ? { value: close, at: fallback.anchor_date, source: 'close' } : null;
}

const SESSION_MINUTES = 390;   // 09:30-16:00 ET (early closes and holidays ignored: a small error mid-week)

/** Minutes since midnight and weekday in New York for `d`. */
function newYork(d: Date) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', hour12: false, weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  }).formatToParts(d).map((p) => [p.type, p.value]));
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    weekend: parts.weekday === 'Sat' || parts.weekday === 'Sun',
    minutes: (Number(parts.hour) % 24) * 60 + Number(parts.minute),
  };
}

const weekdaysBetween = (from: string, to: string) => {  // weekdays d with from < d <= to (dates as YYYY-MM-DD)
  let n = 0;
  for (let d = new Date(`${from}T12:00:00Z`); ;) {
    d = new Date(d.getTime() + 86_400_000);
    const iso = d.toISOString().slice(0, 10);
    if (iso > to) return n;
    if (d.getUTCDay() !== 0 && d.getUTCDay() !== 6) n += 1;
  }
};

/**
 * Share of the forecast week's trading time still ahead: 1 at the anchor's close, 0 at the expiry's close.
 * Today counts for the part of its session not yet traded.
 */
export function fractionLeft(anchor: string, expiry: string, now: Date = new Date()): number {
  const week = weekdaysBetween(anchor, expiry) * SESSION_MINUTES;
  const ny = newYork(now);
  if (ny.date <= anchor) return 1;
  if (ny.date > expiry) return 0;
  const today = ny.weekend ? 0 : Math.min(Math.max(16 * 60 - Math.max(ny.minutes, 9 * 60 + 30), 0), SESSION_MINUTES);
  const ahead = weekdaysBetween(ny.date, expiry) * SESSION_MINUTES + today;
  return week > 0 ? Math.min(Math.max(ahead / week, 0), 1) : 0;
}

export type Regime ={ label: 'calm' | 'normal' | 'stressed'; description: string };

/** Same VIX bands as the forecast's monitoring (calm < 15 <= normal < 25 <= stressed). */
export function regimeOf(vix: number): Regime {
  if (vix < 15) return { label: 'calm', description: 'VIX below 15: ranges are narrow and the forecast tends to sit inside them' };
  if (vix < 25) return { label: 'normal', description: 'VIX 15-25: typical conditions' };
  return { label: 'stressed', description: 'VIX 25 or higher: wide ranges; calibrated bands matter most here' };
}

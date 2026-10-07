/** Shapes and helpers for the live SPX quote served by market-stream (GET /v1/quotes/SPX). */

export const STREAM_API = process.env.NEXT_PUBLIC_MARKET_STREAM_API ?? 'http://localhost:8090';

export type LiveLeg = {
  identifier?: string;
  strike: number;
  option_type: 'CALL' | 'PUT';
  expiry: string;
  bid?: number | null;
  ask?: number | null;
  last?: number | null;
  volume?: number | null;
  open_interest?: number | null;
  iv?: number | null;
  delta?: number | null;
};

export type ExpirySummary = {
  expiry: string;
  dte: number;
  atm_iv?: number | null;
  forward?: number | null;
  quoted_at?: string | null;
};

export type LiveQuote = {
  symbol: string;
  last_price: number;
  timestamp?: string;
  spot_iv?: number | null;
  legs: LiveLeg[];
  expiries?: ExpirySummary[];
  default_expiry?: string | null;
  source?: string | null;
  delay_minutes?: number | null;
  quoted_at?: string | null;
};

/** Bid/ask mid when two-sided, else the last trade, else whichever side exists (same rule as the simulator). */
export const legMid = (leg?: LiveLeg | null): number | null => {
  if (!leg) return null;
  const { bid, ask, last } = leg;
  if (bid && ask && ask >= bid) return (bid + ask) / 2;
  return last || bid || ask || null;
};

/** Expiries in the quote, falling back to the distinct leg expiries for older publishers. */
export const quoteExpiries = (quote: LiveQuote | null): ExpirySummary[] => {
  if (!quote) return [];
  if (quote.expiries?.length) return quote.expiries;
  const today = new Date();
  return Array.from(new Set(quote.legs.map((l) => l.expiry)))
    .sort()
    .map((expiry) => ({
      expiry,
      dte: Math.max(0, Math.round((new Date(`${expiry}T00:00:00`).getTime() - today.getTime()) / 86_400_000))
    }));
};

export const defaultExpiry = (quote: LiveQuote | null): string | null =>
  quote?.default_expiry ?? quoteExpiries(quote)[0]?.expiry ?? null;

/** "Oct 7" from "2026-10-07", without timezone drift. */
export const expiryLabel = (expiry: string) =>
  new Date(`${expiry}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

export const pct = (value?: number | null, digits = 1) =>
  value === null || value === undefined ? '–' : `${(value * 100).toFixed(digits)}%`;

const SOURCE_LABELS: Record<string, string> = { cboe: 'CBOE', yahoo: 'Yahoo' };

/** "Delayed 15 min · CBOE · as of 16:14 ET" (with the date when it isn't today). */
export const feedLabel = (quote: LiveQuote) => {
  const parts: string[] = [];
  if (quote.delay_minutes) parts.push(`Delayed ${quote.delay_minutes} min`);
  else if (quote.delay_minutes === 0) parts.push('Real-time');
  if (quote.source) parts.push(SOURCE_LABELS[quote.source] ?? quote.source);
  if (quote.quoted_at) {
    const at = new Date(quote.quoted_at);
    const opts: Intl.DateTimeFormatOptions = { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false };
    if (at.toDateString() !== new Date().toDateString()) Object.assign(opts, { month: 'short', day: 'numeric' });
    parts.push(`as of ${at.toLocaleString('en-US', opts)} ET`);
  }
  return parts.join(' · ');
};

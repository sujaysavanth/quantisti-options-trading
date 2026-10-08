/**
 * Position Greeks of a strategy, from its legs' implied vols (Black-Scholes-Merton, like the market service).
 * Delta comes from the quote when it has one; gamma, theta and vega are computed. Dollars per lot:
 *   delta  SPX-point delta x 100 (dollars per 1-point move)
 *   gamma  change in that delta per 1-point move
 *   theta  dollars per calendar day
 *   vega   dollars per 1 volatility point
 */

import { MULTIPLIER } from './format';
import { normCdf } from './distribution';
import type { OptionLeg } from './types';

const RATE = 0.04;              // ~3-month T-bill; the market service uses FRED's rate per day
const DIVIDEND_YIELD = 0.013;   // same as market_spec.DIVIDEND_YIELD
const YEAR_MS = 365 * 24 * 3600 * 1000;

const pdf = (x: number) => Math.exp(-(x * x) / 2) / Math.sqrt(2 * Math.PI);

/** Years from `now` to the expiry's 16:00 ET close (EDT offset; an hour off in winter, immaterial here). */
export function yearsToExpiry(expiry: string, now: Date = new Date()): number {
  const close = Date.parse(`${expiry}T16:00:00-04:00`);
  return Math.max((close - now.getTime()) / YEAR_MS, 1 / (365 * 24));
}

export function legGreeks(leg: OptionLeg, spot: number, now: Date = new Date()) {
  const sigma = leg.iv ?? 0;
  if (!(sigma > 0)) return null;
  const t = yearsToExpiry(leg.expiry, now);
  const sqrtT = Math.sqrt(t);
  const d1 = (Math.log(spot / leg.strike) + (RATE - DIVIDEND_YIELD + (sigma * sigma) / 2) * t) / (sigma * sqrtT);
  const d2 = d1 - sigma * sqrtT;
  const disc = Math.exp(-DIVIDEND_YIELD * t);
  const call = leg.optionType === 'CALL';
  const bsDelta = call ? disc * normCdf(d1) : disc * (normCdf(d1) - 1);
  const decay = (-spot * disc * pdf(d1) * sigma) / (2 * sqrtT);
  const carry = call
    ? -RATE * leg.strike * Math.exp(-RATE * t) * normCdf(d2) + DIVIDEND_YIELD * spot * disc * normCdf(d1)
    : RATE * leg.strike * Math.exp(-RATE * t) * normCdf(-d2) - DIVIDEND_YIELD * spot * disc * normCdf(-d1);
  return {
    delta: leg.delta ?? bsDelta,
    gamma: (disc * pdf(d1)) / (spot * sigma * sqrtT),
    theta: (decay + carry) / 365,
    vega: spot * disc * pdf(d1) * sqrtT * 0.01,
  };
}

export type PositionGreeks = { delta: number; gamma: number; theta: number; vega: number; missing: number };

/** Sum over legs (signed, x quantity x multiplier). `missing` counts legs without an implied vol. */
export function positionGreeks(legs: OptionLeg[], spot: number, now: Date = new Date()): PositionGreeks {
  const total: PositionGreeks = { delta: 0, gamma: 0, theta: 0, vega: 0, missing: 0 };
  for (const leg of legs) {
    const g = legGreeks(leg, spot, now);
    if (!g) {
      total.missing += 1;
      continue;
    }
    const k = (leg.action === 'BUY' ? 1 : -1) * (leg.quantity ?? 1) * MULTIPLIER;
    total.delta += g.delta * k;
    total.gamma += g.gamma * k;
    total.theta += g.theta * k;
    total.vega += g.vega * k;
  }
  return total;
}

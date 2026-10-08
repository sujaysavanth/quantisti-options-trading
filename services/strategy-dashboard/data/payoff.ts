/** Expiry payoff of option strategies: P&L curve, max profit / loss, breakevens. Dollars per lot. */

import { MULTIPLIER } from './format';
import type { OptionLeg, PayoffPoint } from './types';

const sign = (leg: Pick<OptionLeg, 'action'>) => (leg.action === 'BUY' ? 1 : -1);

/** One leg's P&L at expiry if SPX settles at `price` (premium paid or received included). */
export function legPl(leg: OptionLeg, price: number): number {
  const intrinsic = leg.optionType === 'CALL' ? Math.max(price - leg.strike, 0) : Math.max(leg.strike - price, 0);
  return (intrinsic - (leg.premium ?? 0)) * MULTIPLIER * sign(leg) * (leg.quantity ?? 1);
}

export const strategyPl = (legs: OptionLeg[], price: number) => legs.reduce((sum, leg) => sum + legPl(leg, price), 0);

/** P&L curve on a 5-point grid around spot and the strikes, for charts. */
export function payoffCurve(legs: OptionLeg[], spot: number, pad = 150, step = 5): PayoffPoint[] {
  if (!legs.length) return [];
  const strikes = legs.map((l) => l.strike);
  const lo = Math.floor((Math.min(spot, ...strikes) - pad) / step) * step;
  const hi = Math.ceil((Math.max(spot, ...strikes) + pad) / step) * step;
  const points: PayoffPoint[] = [];
  for (let p = lo; p <= hi; p += step) points.push({ price: p, pl: Math.round(strategyPl(legs, p)) });
  return points;
}

/**
 * Max profit, max loss and breakevens, exactly: the payoff is linear between strikes, so it is enough to
 * look at 0, each strike and the slope beyond the highest strike (net long calls: unlimited profit; net short
 * calls: unlimited loss).
 */
export function payoffStats(legs: OptionLeg[]) {
  const strikes = Array.from(new Set(legs.map((l) => l.strike))).sort((a, b) => a - b);
  const netCalls = legs.filter((l) => l.optionType === 'CALL').reduce((s, l) => s + sign(l) * (l.quantity ?? 1), 0);
  const far = (strikes[strikes.length - 1] ?? 0) * 3;
  const xs = [0, ...strikes, far];
  const ys = xs.map((x) => strategyPl(legs, x));
  const maxProfit = netCalls > 0 ? null : Math.max(...ys);                // net long calls: no ceiling
  const maxLoss = netCalls < 0 ? null : Math.max(0, -Math.min(...ys));    // net short calls: no floor
  const breakevens: number[] = [];
  for (let i = 0; i < xs.length - 1; i++) {
    const [y0, y1] = [ys[i], ys[i + 1]];
    if ((y0 < 0 && y1 > 0) || (y0 > 0 && y1 < 0)) breakevens.push(xs[i] + ((0 - y0) * (xs[i + 1] - xs[i])) / (y1 - y0));
  }
  const netPremium = legs.reduce((s, l) => s - sign(l) * (l.premium ?? 0) * MULTIPLIER * (l.quantity ?? 1), 0);
  const riskReward = maxProfit !== null && maxLoss ? maxProfit / maxLoss : null;
  return { maxProfit, maxLoss, breakevens: breakevens.map((b) => Math.round(b * 100) / 100), netPremium, riskReward };
}

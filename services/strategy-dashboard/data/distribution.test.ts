import { describe, expect, it } from 'vitest';
import { cdf, normCdf, normInv, priceAt, quantileAt, scorePayoff, type QuantileForecast, rescale } from './distribution';
import { fractionLeft } from './forecast';

const Z = { q05: -1.6448536, q10: -1.2815516, q50: 0, q90: 1.2815516, q95: 1.6448536 };
const normalForecast = (sigma: number, spot = 6800): QuantileForecast => ({
  spot,
  quantiles: { q05: sigma * Z.q05, q10: sigma * Z.q10, q50: 0, q90: sigma * Z.q90, q95: sigma * Z.q95 },
});

describe('normal helpers', () => {
  it('cdf and its inverse agree', () => {
    expect(normCdf(1.959964)).toBeCloseTo(0.975, 5);
    expect(normCdf(0)).toBeCloseTo(0.5, 7);
    for (const p of [0.001, 0.02, 0.1, 0.5, 0.8, 0.97, 0.999]) expect(normCdf(normInv(p))).toBeCloseTo(p, 6);
  });
});

describe('quantile function', () => {
  const f = normalForecast(0.022);

  it('passes through the forecast quantiles', () => {
    expect(quantileAt(f.quantiles, 0.05)).toBeCloseTo(f.quantiles.q05, 10);
    expect(quantileAt(f.quantiles, 0.1)).toBeCloseTo(f.quantiles.q10, 10);
    expect(quantileAt(f.quantiles, 0.5)).toBeCloseTo(0, 10);
    expect(quantileAt(f.quantiles, 0.95)).toBeCloseTo(f.quantiles.q95, 10);
  });

  it('cdf inverts it, middle and tails', () => {
    for (const u of [0.001, 0.03, 0.07, 0.3, 0.5, 0.75, 0.92, 0.99]) expect(cdf(f, priceAt(f, u))).toBeCloseTo(u, 6);
  });

  it('normal-shaped tails match a normal distribution far out', () => {
    const price = f.spot * Math.exp(-2.5 * 0.022);
    expect(cdf(f, price)).toBeCloseTo(normCdf(-2.5), 4);
  });
});

describe('scoring a payoff', () => {
  const sigma = 0.022;
  const f = normalForecast(sigma);

  it('a constant payoff', () => {
    const s = scorePayoff(f, () => 150);
    expect(s.expectedPl).toBeCloseTo(150, 6);
    expect(s.probabilityOfProfit).toBe(1);
  });

  it('probability of landing between two strikes is close to the normal answer', () => {
    const [lo, hi] = [6700, 6900];
    const s = scorePayoff(f, (p) => (p > lo && p < hi ? 1 : -1));
    const exact = normCdf(Math.log(hi / f.spot) / sigma) - normCdf(Math.log(lo / f.spot) / sigma);
    expect(Math.abs(s.probabilityOfProfit - exact)).toBeLessThan(0.002);  // exact for a normal forecast
  });

  it('expected value moves with the median', () => {
    const up: QuantileForecast = { spot: 6800, quantiles: { ...f.quantiles,
      q05: f.quantiles.q05 + 0.01, q10: f.quantiles.q10 + 0.01, q50: 0.01, q90: f.quantiles.q90 + 0.01, q95: f.quantiles.q95 + 0.01 } };
    const forward = (p: number) => p - 6800;
    expect(scorePayoff(up, forward).expectedPl).toBeGreaterThan(scorePayoff(f, forward).expectedPl + 50);
  });
});

describe('conditioning the weekly forecast on now', () => {
  const week: QuantileForecast = { spot: 6800, quantiles: { q05: -0.04, q10: -0.03, q50: 0.002, q90: 0.03, q95: 0.04 } };

  it('is the forecast itself at the anchor close', () => {
    expect(rescale(week, 6800, 1)).toEqual(week);
  });

  it('centres on the live price and shrinks the spread by sqrt(time left)', () => {
    const r = rescale(week, 6900, 0.25);
    expect(r.spot).toBe(6900);
    expect(r.quantiles.q50).toBeCloseTo(0.0005, 10);
    expect(r.quantiles.q90 - r.quantiles.q50).toBeCloseTo((0.03 - 0.002) * 0.5, 10);
  });

  it('collapses to the live price at expiry', () => {
    const r = rescale(week, 6900, 0);
    expect(priceAt(r, 0.05)).toBeCloseTo(6900, 6);
    expect(priceAt(r, 0.95)).toBeCloseTo(6900, 6);
  });
});

describe('fraction of the forecast week left', () => {
  // Anchor Fri 2026-10-02, expiry Fri 2026-10-09: five sessions of 390 minutes. Times are EDT (UTC-4).
  const left = (iso: string) => fractionLeft('2026-10-02', '2026-10-09', new Date(iso));
  it('is 1 over the weekend after the anchor', () => expect(left('2026-10-03T15:00:00Z')).toBe(1));
  it('is 1 before Monday opens', () => expect(left('2026-10-05T12:00:00Z')).toBe(1));
  it('is 4/5 at Monday close', () => expect(left('2026-10-05T20:00:00Z')).toBeCloseTo(0.8, 10));
  it('counts the untraded part of today', () => expect(left('2026-10-08T17:45:00Z')).toBeCloseTo((390 + 135) / 1950, 10));
  it('is 0 at expiry close', () => expect(left('2026-10-09T20:00:00Z')).toBe(0));
});

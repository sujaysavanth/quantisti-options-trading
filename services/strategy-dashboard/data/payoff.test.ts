import { describe, expect, it } from 'vitest';
import { payoffCurve, payoffStats, strategyPl } from './payoff';
import { positionGreeks } from './greeks';
import type { OptionLeg } from './types';

const leg = (action: 'BUY' | 'SELL', optionType: 'CALL' | 'PUT', strike: number, premium: number, iv = 0.15): OptionLeg => ({
  action, optionType, strike, premium, iv, expiry: '2026-10-16', projectedPl: 0, payoffPoints: [],
});

// Credit 6.0 + 5.5 - 2.0 - 1.5 = 8.0 points = $800; wings 25 points wide.
const condor = [leg('SELL', 'PUT', 6750, 6.0), leg('BUY', 'PUT', 6725, 2.0), leg('SELL', 'CALL', 6850, 5.5), leg('BUY', 'CALL', 6875, 1.5)];

describe('payoff', () => {
  it('iron condor: credit, max loss and breakevens by hand', () => {
    const s = payoffStats(condor);
    expect(s.netPremium).toBeCloseTo(800, 6);
    expect(s.maxProfit).toBeCloseTo(800, 6);
    expect(s.maxLoss).toBeCloseTo(25 * 100 - 800, 6);
    expect(s.breakevens).toEqual([6742, 6858]);
    expect(s.riskReward).toBeCloseTo(800 / 1700, 6);
    expect(strategyPl(condor, 6800)).toBeCloseTo(800, 6);
  });

  it('naked short call: unlimited loss; long call: unlimited profit', () => {
    expect(payoffStats([leg('SELL', 'CALL', 6850, 5)]).maxLoss).toBeNull();
    const long = payoffStats([leg('BUY', 'CALL', 6850, 5)]);
    expect(long.maxProfit).toBeNull();
    expect(long.maxLoss).toBeCloseTo(500, 6);
    expect(long.breakevens).toEqual([6855]);
  });

  it('curve covers spot and strikes on a 5-point grid', () => {
    const curve = payoffCurve(condor, 6800);
    expect(curve[0].price).toBeLessThanOrEqual(6725 - 150);
    expect(curve[curve.length - 1].price).toBeGreaterThanOrEqual(6875 + 150);
    expect(curve.every((p, i) => i === 0 || p.price - curve[i - 1].price === 5)).toBe(true);
  });
});

describe('greeks', () => {
  const now = new Date('2026-10-09T14:00:00Z');

  it('a short iron condor is short gamma and vega, long theta, roughly delta-neutral', () => {
    const g = positionGreeks(condor, 6800, now);
    expect(g.missing).toBe(0);
    expect(g.gamma).toBeLessThan(0);
    expect(g.vega).toBeLessThan(0);
    expect(g.theta).toBeGreaterThan(0);
    expect(Math.abs(g.delta)).toBeLessThan(10);                            // vs +-100 for one ATM call
  });

  it('call minus put delta at the same strike is the dividend discount (~1)', () => {
    const call = positionGreeks([leg('BUY', 'CALL', 6800, 50)], 6800, now).delta;
    const put = positionGreeks([leg('BUY', 'PUT', 6800, 50)], 6800, now).delta;
    expect((call - put) / 100).toBeCloseTo(1, 2);
    expect(call / 100).toBeGreaterThan(0.45);
    expect(call / 100).toBeLessThan(0.6);
  });

  it('legs without an implied vol are counted, not guessed', () => {
    const g = positionGreeks([{ ...condor[0], iv: null }, condor[1]], 6800, now);
    expect(g.missing).toBe(1);
  });

  it('a quoted delta is used as given', () => {
    const g = positionGreeks([{ ...leg('BUY', 'CALL', 6800, 50), delta: 0.42 }], 6800, now);
    expect(g.delta).toBeCloseTo(42, 6);
  });
});

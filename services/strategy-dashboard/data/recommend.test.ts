import { describe, expect, it } from 'vitest';
import { fitStrategy, rankStrategies, spreadCost, stickyPick } from './recommend';
import { payoffStats } from './payoff';
import type { OptionLeg, StrategyRecommendation } from './types';

const leg = (action: 'BUY' | 'SELL', optionType: 'CALL' | 'PUT', strike: number, premium: number, halfSpread: number | null = 0.25): OptionLeg =>
  ({ action, optionType, strike, premium, expiry: '2026-10-09', quantity: 1, halfSpread, projectedPl: 0, payoffPoints: [] });

const strategy = (name: string, legs: OptionLeg[]): StrategyRecommendation =>
  ({ name, type: 't', strikes: '', expiry: '2026-10-09', ...payoffStats(legs), payoffPoints: [], legs, forecast: null });

// A wide forecast centred on 6800 (about +-3% at 80%): it favours buying volatility.
const wide = { spot: 6800, quantiles: { q05: -0.04, q10: -0.03, q50: 0, q90: 0.03, q95: 0.04 } };

describe('spread cost', () => {
  it('charges half the spread per leg, x100', () => {
    expect(spreadCost([leg('BUY', 'CALL', 6800, 40), leg('SELL', 'CALL', 6850, 20)]).cost).toBeCloseTo(50);
  });
  it('flags legs without a two-sided quote', () => {
    expect(spreadCost([leg('BUY', 'CALL', 6800, 40, null)])).toEqual({ cost: 0, unknown: 1 });
  });
});

describe('ranking', () => {
  const debitSpread = strategy('Bull Call Spread', [leg('BUY', 'CALL', 6800, 40), leg('SELL', 'CALL', 6850, 20)]);
  const straddle = strategy('Long Straddle', [leg('BUY', 'CALL', 6800, 40), leg('BUY', 'PUT', 6800, 40)]);
  const shortStraddle = strategy('Short Straddle', [leg('SELL', 'CALL', 6800, 40), leg('SELL', 'PUT', 6800, 40)]);

  it('return on risk is net expected P&L over max loss, and undefined risk has none', () => {
    const f = fitStrategy(straddle, wide, 'garch');
    expect(f.netExpectedPl).toBeCloseTo(f.expectedPl - 50);
    expect(f.returnOnRisk).toBeCloseTo(f.netExpectedPl / 8000);
    expect(fitStrategy(shortStraddle, wide, 'garch').returnOnRisk).toBeNull();
  });

  it('picks the best defined-risk strategy and never an undefined-risk one', () => {
    const fitted = [shortStraddle, debitSpread, straddle].map((s) => ({ ...s, forecast: fitStrategy(s, wide, 'garch') }));
    const { ranked, pick } = rankStrategies(fitted);
    expect(pick?.name).toBe('Long Straddle');                                   // wide forecast, cheap straddle
    expect(ranked[ranked.length - 1].name).toBe('Short Straddle');              // undefined risk ranks after defined
  });

  it('stands aside when nothing is positive after costs', () => {
    const tight = { spot: 6800, quantiles: { q05: -0.004, q10: -0.003, q50: 0, q90: 0.003, q95: 0.004 } };
    const fitted = [straddle].map((s) => ({ ...s, forecast: fitStrategy(s, tight, 'garch') }));
    expect(rankStrategies(fitted).pick).toBeNull();
  });

  it('has no pick without a forecast', () => {
    expect(rankStrategies([debitSpread, straddle]).pick).toBeNull();
  });
});

describe('sticky pick', () => {
  const s = (name: string, ror: number, net = 100): StrategyRecommendation => ({
    ...strategy(name, [leg('BUY', 'CALL', 6800, 40)]),
    forecast: { probabilityOfProfit: 0.5, expectedPl: net, method: 'garch', spreadCost: 0, spreadUnknown: 0, netExpectedPl: net, returnOnRisk: ror },
  });
  it('keeps the previous pick when the new leader is only slightly ahead', () => {
    expect(stickyPick(rankStrategies([s('A', 0.110), s('B', 0.100)]), 'B')?.name).toBe('B');
  });
  it('switches when the new leader is clearly ahead', () => {
    expect(stickyPick(rankStrategies([s('A', 0.150), s('B', 0.100)]), 'B')?.name).toBe('A');
  });
  it('drops a previous pick that is no longer positive after costs', () => {
    expect(stickyPick(rankStrategies([s('A', 0.050), s('B', -0.01, -10)]), 'B')?.name).toBe('A');
  });
  it('stands aside even if the previous pick was something', () => {
    expect(stickyPick(rankStrategies([s('B', -0.01, -10)]), 'B')).toBeNull();
  });
});

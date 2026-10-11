import { describe, expect, it } from 'vitest';
import { equitySeries, pct, pnlTint, stressMatrix, type Snapshot, type Stress, type StressRow } from './portfolio';

const snap = (t: string, value: number, spot: number | null): Snapshot => ({
  kind: 'close', taken_at: t, session: t.slice(0, 10), starting_balance: 30_000, account_value: value,
  realised_pnl: 0, unrealised_pnl: 0, capital_held: 0, available: 0, open_trades: 0, spot,
});

describe('equitySeries', () => {
  it('rebases SPX to the first account value and tracks drawdown from the starting balance', () => {
    const s = equitySeries(
      [snap('2026-10-13T20:00:00Z', 31_000, 6900), snap('2026-10-12T20:00:00Z', 29_000, 6800), snap('2026-10-14T20:00:00Z', 30_380, 6936)],
      30_000,
    );
    expect(s.map((p) => p.value)).toEqual([29_000, 31_000, 30_380]);          // sorted by time
    expect(s[0].spx).toBeCloseTo(29_000, 6);
    expect(s[1].spx).toBeCloseTo((29_000 * 6900) / 6800, 6);
    expect(s[0].drawdown).toBeCloseTo(29_000 / 30_000 - 1, 9);                // below the starting balance
    expect(s[1].drawdown).toBe(0);
    expect(s[2].drawdown).toBeCloseTo(30_380 / 31_000 - 1, 9);
  });

  it('leaves SPX empty when no snapshot has a price', () => {
    expect(equitySeries([snap('2026-10-12T20:00:00Z', 30_000, null)], 30_000)[0].spx).toBeNull();
  });
});

describe('stressMatrix', () => {
  const row = (m: number, iv: number, days: number, pnl: number): StressRow => ({
    name: '', date: null, spx_move: m, iv_shift: iv, days, pnl, pct_of_account: null, account_value_after: 0,
    capital_held_after: null, available_after: null, short_of_capital: false,
  });
  const moves = [-0.05, 0, 0.05];
  const ivs = [-5, 0, 10];
  const grid = [0, 1].flatMap((d) => ivs.flatMap((iv) => moves.map((m) => row(m, iv, d, m * 1000 + iv + d * 0.5))));
  const stress = { axes: { spx_moves: moves, iv_shifts: ivs, horizons_days: [0, 1] }, grid } as unknown as Stress;

  it('lays out one horizon with the largest IV shift on top', () => {
    const mx = stressMatrix(stress, 1);
    expect(mx.map((r) => r.ivShift)).toEqual([10, 0, -5]);
    expect(mx[0].cells.map((c) => c.pnl)).toEqual([-50 + 10.5, 10.5, 50 + 10.5]);
    expect(mx.every((r) => r.cells.every((c) => c.days === 1))).toBe(true);
  });
});

describe('formatting', () => {
  it('pct and tint', () => {
    expect(pct(0.0123)).toBe('+1.23%');
    expect(pct(-0.5, 0)).toBe('-50%');
    expect(pct(null)).toBe('–');
    expect(pnlTint(0, 100)).toBe('transparent');
    expect(pnlTint(100, 100)).toContain('16, 185, 129');
    expect(pnlTint(-500, 100)).toBe('rgba(244, 63, 94, 0.630)');            // capped at full strength
  });
});

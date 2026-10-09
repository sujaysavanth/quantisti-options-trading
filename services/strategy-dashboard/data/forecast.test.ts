import { describe, expect, it } from 'vitest';
import { conditionExpiry, type ExpiryForecast } from './forecast';

const z = [-1.7, -1.3, 0.0, 1.3, 1.7];
const e: ExpiryForecast = {
  expiry_date: '2026-10-12', sessions: 2, quantiles: { q05: 0, q10: 0, q50: 0, q90: 0, q95: 0 }, range_80: [0, 0], range_90: [0, 0],
  sigma: Math.sqrt(0.0001 + 0.0002), z, variance_path: [0.0001, 0.0002], path_dates: ['2026-10-09', '2026-10-12'],
  validation: { valid: true, reason: 'ok' },
};
// Times in EDT (UTC-4).
const at = (iso: string) => conditionExpiry(e, 7800, new Date(iso));

describe('an expiry forecast conditioned on the quotes\' time', () => {
  it('uses the whole path before the first session opens', () => {
    const c = at('2026-10-09T12:00:00Z');                        // 08:00 ET Friday
    expect(c.dist!.quantiles.q90).toBeCloseTo(1.3 * Math.sqrt(0.0003), 12);
    expect(c.dist!.spot).toBe(7800);
    expect(c.intraday).toBe(false);
  });
  it('removes the traded share of today', () => {
    const c = at('2026-10-09T17:45:00Z');                        // 13:45 ET: 135 of 390 minutes left
    expect(c.dist!.quantiles.q90).toBeCloseTo(1.3 * Math.sqrt(0.0001 * 135 / 390 + 0.0002), 12);
  });
  it('flags a same-day expiry once its session has started', () => {
    const today = { ...e, expiry_date: '2026-10-09', sessions: 1, variance_path: [0.0001], path_dates: ['2026-10-09'] };
    expect(conditionExpiry(today, 7800, new Date('2026-10-09T15:00:00Z')).intraday).toBe(true);
    expect(conditionExpiry(today, 7800, new Date('2026-10-09T21:00:00Z')).dist).toBeNull();   // after the close: settled
  });
  it('drops sessions that have closed', () => {
    const c = at('2026-10-10T15:00:00Z');                        // Saturday: only Monday is left
    expect(c.dist!.quantiles.q90).toBeCloseTo(1.3 * Math.sqrt(0.0002), 12);
  });
  it('shows nothing for a horizon that failed validation', () => {
    const c = conditionExpiry({ ...e, validation: { valid: false, reason: '80% band held 70% of the time' } }, 7800, new Date());
    expect(c.dist).toBeNull();
    expect(c.reason).toContain('70%');
  });
});

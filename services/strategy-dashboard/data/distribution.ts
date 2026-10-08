/**
 * Turn the weekly forecast's five quantiles into a full distribution of next expiry's close, and use it to
 * score a strategy: probability of profit and expected P&L.
 *
 * The forecast gives the 5%, 10%, 50%, 90% and 95% quantiles of the log return to expiry. The quantile
 * function is interpolated in normal-score space: the log return is piecewise linear in z = Phi^-1(u), through
 * the five points (z of each level, its quantile), and the end segments continue into the tails. For a normal
 * forecast this is exact; for a skewed or fat-tailed one it bends smoothly. (Interpolating linearly in u
 * instead misjudges the middle badly: by ~8 percentage points for strikes +-1.5% from spot.) Expectations
 * are averages over N equally spaced probabilities.
 */

export type Quantiles = { q05: number; q10: number; q50: number; q90: number; q95: number };
export type QuantileForecast = { spot: number; quantiles: Quantiles };

const Z05 = -1.6448536269514722;
const Z10 = -1.2815515655446004;

/** Standard normal CDF (Abramowitz & Stegun 7.1.26 via erf; absolute error < 1.5e-7). */
export function normCdf(x: number): number {
  const t = 1 / (1 + 0.3275911 * Math.abs(x) / Math.SQRT2);
  const poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))));
  const erf = 1 - poly * Math.exp(-(x * x) / 2);
  return x >= 0 ? (1 + erf) / 2 : (1 - erf) / 2;
}

/** Inverse standard normal CDF (Acklam's rational approximation; relative error < 1.2e-9). */
export function normInv(p: number): number {
  if (p <= 0) return -Infinity;
  if (p >= 1) return Infinity;
  const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239];
  const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572];
  const c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
  const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
  const low = 0.02425;
  if (p < low) {
    const q = Math.sqrt(-2 * Math.log(p));
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  if (p > 1 - low) return -normInv(1 - p);
  const q = p - 0.5;
  const r = q * q;
  return ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) /
    (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
}

const ZK = [Z05, Z10, 0, -Z10, -Z05];            // normal scores of the 5/10/50/90/95% levels

const knotsOf = (q: Quantiles) => [q.q05, q.q10, q.q50, q.q90, q.q95];

/** Piecewise-linear interpolation through (xs, ys), extended linearly beyond both ends. */
function interp(x: number, xs: number[], ys: number[]): number {
  let i = 0;
  while (i < xs.length - 2 && x > xs[i + 1]) i++;            // segment [i, i+1]; ends extrapolate
  const span = xs[i + 1] - xs[i];
  return span > 0 ? ys[i] + ((x - xs[i]) * (ys[i + 1] - ys[i])) / span : ys[i];
}

/** Log return at probability u (0 < u < 1). */
export function quantileAt(q: Quantiles, u: number): number {
  return interp(normInv(u), ZK, knotsOf(q));
}

/** Probability that the close at expiry is at or below `price`. */
export function cdf(f: QuantileForecast, price: number): number {
  return normCdf(interp(Math.log(price / f.spot), knotsOf(f.quantiles), ZK));
}

/**
 * The weekly forecast (made at the anchor's close, for the whole week) conditioned on now: centred on the
 * current spot, spread scaled by sqrt(fraction of the week's trading time left) and drift by that fraction.
 * At the anchor's close (fraction 1, same spot) it is the forecast itself. Without this, mid-week scoring
 * compares options with a day left against a week-long distribution centred on last Friday's price.
 */
export function rescale(f: QuantileForecast, spotNow: number, fraction: number): QuantileForecast {
  const k = Math.min(Math.max(fraction, 0), 1);
  const m = f.quantiles.q50;
  const scale = (x: number) => m * k + (x - m) * Math.sqrt(k);
  const q = f.quantiles;
  return { spot: spotNow, quantiles: { q05: scale(q.q05), q10: scale(q.q10), q50: m * k, q90: scale(q.q90), q95: scale(q.q95) } };
}

/** Index level at probability u. */
export const priceAt = (f: QuantileForecast, u: number) => f.spot * Math.exp(quantileAt(f.quantiles, u));

/** Probability of profit and expected P&L of a payoff (dollars at expiry as a function of the close). */
export function scorePayoff(f: QuantileForecast, payoff: (price: number) => number, n = 4000) {
  let total = 0;
  let wins = 0;
  for (let i = 0; i < n; i++) {
    const value = payoff(priceAt(f, (i + 0.5) / n));
    total += value;
    if (value > 0) wins += 1;
  }
  return { probabilityOfProfit: wins / n, expectedPl: total / n };
}

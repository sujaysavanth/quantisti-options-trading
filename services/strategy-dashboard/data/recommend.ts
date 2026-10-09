/**
 * Which strategy fits the forecast best, ranked on numbers that hold up rather than a made-up score.
 *
 *   spread cost      what crossing the bid/ask costs to open: half the spread on every leg, x100 per contract
 *   net expected    expected P&L under the forecast (priced at mids) minus that cost
 *   return on risk   net expected / max loss: comparable across a $900 spread and a $4,700 straddle
 *
 * The pick is the defined-risk strategy with the best return on risk, if its net expected P&L is positive.
 * Undefined-risk strategies are listed but never picked: with no max loss there is no return on risk, and the
 * pick should never be one whose loss has no floor. If nothing is positive after costs, there is no pick:
 * "stand aside" is a legitimate answer.
 */

import { scorePayoff, type QuantileForecast } from './distribution';
import { strategyPl } from './payoff';
import type { ForecastFit, OptionLeg, StrategyRecommendation } from './types';

export const MULTIPLIER = 100;

/** Dollars to cross half the bid/ask on every leg (unknown spreads count as zero and are flagged). */
export function spreadCost(legs: OptionLeg[]): { cost: number; unknown: number } {
  let cost = 0;
  let unknown = 0;
  for (const leg of legs) {
    if (leg.halfSpread == null) unknown += 1;
    else cost += leg.halfSpread * MULTIPLIER * (leg.quantity ?? 1);
  }
  return { cost, unknown };
}

export function fitStrategy(s: StrategyRecommendation, dist: QuantileForecast, method: string): ForecastFit {
  const { probabilityOfProfit, expectedPl } = scorePayoff(dist, (p) => strategyPl(s.legs, p));
  const { cost, unknown } = spreadCost(s.legs);
  const netExpectedPl = expectedPl - cost;
  return {
    probabilityOfProfit, expectedPl, method, spreadCost: cost, spreadUnknown: unknown, netExpectedPl,
    returnOnRisk: s.maxLoss !== null && s.maxLoss > 0 ? netExpectedPl / s.maxLoss : null,
  };
}

export type Ranking = { ranked: StrategyRecommendation[]; pick: StrategyRecommendation | null };

/** Defined risk by return on risk, then undefined risk by net expected P&L, then strategies with no forecast. */
export function rankStrategies(strategies: StrategyRecommendation[]): Ranking {
  const tier = (s: StrategyRecommendation) => (!s.forecast ? 2 : s.forecast.returnOnRisk === null ? 1 : 0);
  const ranked = [...strategies].sort((a, b) => {
    const t = tier(a) - tier(b);
    if (t !== 0) return t;
    if (!a.forecast || !b.forecast) return 0;
    return a.forecast.returnOnRisk !== null && b.forecast.returnOnRisk !== null
      ? b.forecast.returnOnRisk - a.forecast.returnOnRisk
      : b.forecast.netExpectedPl - a.forecast.netExpectedPl;
  });
  const top = ranked[0];
  const pick = top?.forecast && top.forecast.returnOnRisk !== null && top.forecast.netExpectedPl > 0 ? top : null;
  return { ranked, pick };
}

/** Return-on-risk lead (percentage points / 100) a challenger needs to replace the current pick. */
export const SWITCH_MARGIN = 0.02;

/**
 * Keep the previous pick unless another strategy now beats it clearly. Each new chain moves every estimate a
 * little; without this, near-tied strategies trade places on noise and the recommendation flickers.
 */
export function stickyPick(ranking: Ranking, previous: string | null, margin = SWITCH_MARGIN): StrategyRecommendation | null {
  const { ranked, pick } = ranking;
  if (!pick || !previous || pick.name === previous) return pick;
  const prev = ranked.find((s) => s.name === previous);
  const f = prev?.forecast;
  if (!prev || !f || f.returnOnRisk === null || f.netExpectedPl <= 0) return pick;    // gone, or no longer worth it
  return (pick.forecast!.returnOnRisk ?? 0) - f.returnOnRisk < margin ? prev : pick;
}

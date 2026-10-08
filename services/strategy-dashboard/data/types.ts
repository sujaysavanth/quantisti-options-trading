/** Shapes shared by the dashboard's strategy views. */

export interface PayoffPoint {
  price: number;
  pl: number;
}

export interface OptionLeg {
  identifier?: string;
  action: 'BUY' | 'SELL';
  optionType: 'CALL' | 'PUT';
  quantity?: number;
  strike: number;
  expiry: string;
  /** Per-contract price in index points (the leg's mid). */
  premium: number;
  /** From the live quote, when the chain has them. */
  iv?: number | null;
  delta?: number | null;
  /** P&L at expiry if SPX settles at today's spot, in dollars. */
  projectedPl: number;
  payoffPoints: PayoffPoint[];
}

/** Probability of profit and expected P&L under the weekly range forecast (only for its own expiry). */
export interface ForecastFit {
  probabilityOfProfit: number;
  expectedPl: number;
  method: string;
}

export interface StrategyRecommendation {
  name: string;
  type: string;
  strikes: string;
  expiry: string;
  /** Dollars per 1 lot; null when unlimited. */
  maxProfit: number | null;
  maxLoss: number | null;
  breakevens: number[];
  /** Max profit / max loss; null when either side is unlimited. */
  riskReward: number | null;
  /** Net premium: positive = credit received, negative = debit paid (dollars). */
  netPremium: number;
  payoffPoints: PayoffPoint[];
  legs: OptionLeg[];
  forecast?: ForecastFit | null;
}

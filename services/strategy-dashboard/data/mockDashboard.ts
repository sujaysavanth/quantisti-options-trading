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
  premium: number;
  projectedPl: number;
  marginImpact: number;
  payoffPoints: PayoffPoint[];
}

export interface StrategyRecommendation {
  name: string;
  type: string;
  strikes: string;
  expectedPl: number;
  maxLoss: number;
  winProbability: number;
  riskReward: number;
  margin: number;
  score: number;
  payoffPoints: PayoffPoint[];
  legs: OptionLeg[];
}

export interface DashboardData {
  weekOf: string;
  expiry: string;
  predictedRange: {
    lower: number;
    upper: number;
    confidence: number;
  };
  closingPriceEstimate: number;
  context: {
    vix: number;
    oiPcr: number;
    trend: string;
  };
  strategies: StrategyRecommendation[];
  greeks: {
    delta: number;
    gamma: number;
    theta: number;
    vega: number;
    rho: number;
  };
}

export const dashboardMock: DashboardData = {
  weekOf: '18 Nov 2025',
  expiry: '25 Nov 2025 (Tuesday)',
  predictedRange: {
    lower: 19520,
    upper: 20080,
    confidence: 82
  },
  closingPriceEstimate: 19810,
  context: {
    vix: 13.2,
    oiPcr: 1.11,
    trend: 'Mild uptrend with accelerating momentum'
  },
  strategies: [
    {
      name: 'Balanced Iron Condor',
      type: 'Neutral Income',
      strikes: '19500 / 20100',
      expectedPl: 14800,
      maxLoss: 22000,
      winProbability: 0.68,
      riskReward: 1.9,
      margin: 265000,
    score: 91,
    payoffPoints: [
      { price: 19200, pl: -42000 },
      { price: 19500, pl: 2000 },
      { price: 19800, pl: 16500 },
      { price: 20000, pl: 14800 },
      { price: 20350, pl: -32000 }
    ],
    legs: [
      {
        action: 'SELL',
        optionType: 'CALL',
        strike: 20100,
        expiry: '25 Nov 2025',
        premium: 145,
        projectedPl: 6000,
        marginImpact: 85000,
        payoffPoints: [
          { price: 19500, pl: 8000 },
          { price: 19800, pl: 6000 },
          { price: 20100, pl: 2000 },
          { price: 20400, pl: -6000 }
        ]
      },
      {
        action: 'BUY',
        optionType: 'CALL',
        strike: 20300,
        expiry: '25 Nov 2025',
        premium: 90,
        projectedPl: -3000,
        marginImpact: -45000,
        payoffPoints: [
          { price: 19500, pl: -2000 },
          { price: 19800, pl: -1500 },
          { price: 20300, pl: 0 },
          { price: 20600, pl: 2800 }
        ]
      },
      {
        action: 'SELL',
        optionType: 'PUT',
        strike: 19500,
        expiry: '25 Nov 2025',
        premium: 165,
        projectedPl: 9000,
        marginImpact: 90000,
        payoffPoints: [
          { price: 19200, pl: -16000 },
          { price: 19500, pl: 2000 },
          { price: 19800, pl: 6000 }
        ]
      },
      {
        action: 'BUY',
        optionType: 'PUT',
        strike: 19300,
        expiry: '25 Nov 2025',
        premium: 110,
        projectedPl: -2000,
        marginImpact: -55000,
        payoffPoints: [
          { price: 19000, pl: 12000 },
          { price: 19300, pl: 0 },
          { price: 19600, pl: -4000 }
        ]
      }
    ]
  },
  {
      name: 'Call Calendar Spread',
      type: 'Directional Debit',
      strikes: '19800 / 20100',
      expectedPl: 9400,
      maxLoss: 12000,
      winProbability: 0.57,
      riskReward: 1.5,
      margin: 110000,
      score: 82,
      payoffPoints: [
        { price: 19300, pl: -15000 },
        { price: 19650, pl: 2000 },
        { price: 19800, pl: 9400 },
        { price: 20050, pl: 6000 },
        { price: 20300, pl: -8000 }
      ],
      legs: [
        {
          action: 'BUY',
          optionType: 'CALL',
          strike: 19800,
          expiry: '25 Nov 2025',
          premium: 180,
          projectedPl: 6200,
          marginImpact: -65000,
          payoffPoints: [
            { price: 19500, pl: -1200 },
            { price: 19800, pl: 0 },
            { price: 20100, pl: 3200 }
          ]
        },
        {
          action: 'SELL',
          optionType: 'CALL',
          strike: 20100,
          expiry: '02 Dec 2025',
          premium: 220,
          projectedPl: 3200,
          marginImpact: 120000,
          payoffPoints: [
            { price: 19800, pl: 4200 },
            { price: 20100, pl: 2200 },
            { price: 20450, pl: -3200 }
          ]
        }
      ]
  },
  {
      name: 'Bull Put Spread',
      type: 'Directional Credit',
      strikes: '19500 / 19350',
      expectedPl: 7800,
      maxLoss: 17000,
      winProbability: 0.72,
      riskReward: 1.1,
      margin: 185000,
      score: 77,
      payoffPoints: [
        { price: 19200, pl: -17000 },
        { price: 19400, pl: 2000 },
        { price: 19500, pl: 7800 },
        { price: 19800, pl: 4500 },
        { price: 20000, pl: -5000 }
      ],
      legs: [
        {
          action: 'SELL',
          optionType: 'PUT',
          strike: 19500,
          expiry: '25 Nov 2025',
          premium: 140,
          projectedPl: 7200,
          marginImpact: 100000,
          payoffPoints: [
            { price: 19200, pl: -16000 },
            { price: 19500, pl: 1400 },
            { price: 19750, pl: 4200 }
          ]
        },
        {
          action: 'BUY',
          optionType: 'PUT',
          strike: 19350,
          expiry: '25 Nov 2025',
          premium: 95,
          projectedPl: 600,
          marginImpact: -60000,
          payoffPoints: [
            { price: 19050, pl: 6000 },
            { price: 19350, pl: 0 },
            { price: 19600, pl: -2400 }
          ]
        }
      ]
  }
],
  greeks: {
    delta: 0.07,
    gamma: -0.01,
    theta: 4200,
    vega: -1650,
    rho: 110
  }
};

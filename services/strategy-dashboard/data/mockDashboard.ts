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
  weekOf: '28 Sep 2026',
  expiry: '02 Oct 2026 (Friday)',
  predictedRange: {
    lower: 7540,
    upper: 7760,
    confidence: 82
  },
  closingPriceEstimate: 7655,
  context: {
    vix: 13.2,
    oiPcr: 1.11,
    trend: 'Mild uptrend with accelerating momentum'
  },
  strategies: [
    {
      name: 'Balanced Iron Condor',
      type: 'Neutral Income',
      strikes: '7535 / 7765',
      expectedPl: 7620,
      maxLoss: 11330,
      winProbability: 0.68,
      riskReward: 1.9,
      margin: 136520,
    score: 91,
    payoffPoints: [
      { price: 7420, pl: -21640 },
      { price: 7535, pl: 1030 },
      { price: 7650, pl: 8500 },
      { price: 7725, pl: 7620 },
      { price: 7860, pl: -16480 }
    ],
    legs: [
      {
        action: 'SELL',
        optionType: 'CALL',
        strike: 7765,
        expiry: '02 Oct 2026',
        premium: 56.0,
        projectedPl: 3090,
        marginImpact: 43790,
        payoffPoints: [
          { price: 7535, pl: 4120 },
          { price: 7650, pl: 3090 },
          { price: 7765, pl: 1030 },
          { price: 7880, pl: -3090 }
        ]
      },
      {
        action: 'BUY',
        optionType: 'CALL',
        strike: 7845,
        expiry: '02 Oct 2026',
        premium: 34.8,
        projectedPl: -1550,
        marginImpact: -23180,
        payoffPoints: [
          { price: 7535, pl: -1030 },
          { price: 7650, pl: -770 },
          { price: 7845, pl: 0 },
          { price: 7960, pl: 1440 }
        ]
      },
      {
        action: 'SELL',
        optionType: 'PUT',
        strike: 7535,
        expiry: '02 Oct 2026',
        premium: 63.8,
        projectedPl: 4640,
        marginImpact: 46360,
        payoffPoints: [
          { price: 7420, pl: -8240 },
          { price: 7535, pl: 1030 },
          { price: 7650, pl: 3090 }
        ]
      },
      {
        action: 'BUY',
        optionType: 'PUT',
        strike: 7455,
        expiry: '02 Oct 2026',
        premium: 42.5,
        projectedPl: -1030,
        marginImpact: -28330,
        payoffPoints: [
          { price: 7340, pl: 6180 },
          { price: 7455, pl: 0 },
          { price: 7575, pl: -2060 }
        ]
      }
    ]
  },
  {
      name: 'Call Calendar Spread',
      type: 'Directional Debit',
      strikes: '7650 / 7765',
      expectedPl: 4840,
      maxLoss: 6180,
      winProbability: 0.57,
      riskReward: 1.5,
      margin: 56670,
      score: 82,
      payoffPoints: [
        { price: 7455, pl: -7730 },
        { price: 7590, pl: 1030 },
        { price: 7650, pl: 4840 },
        { price: 7745, pl: 3090 },
        { price: 7845, pl: -4120 }
      ],
      legs: [
        {
          action: 'BUY',
          optionType: 'CALL',
          strike: 7650,
          expiry: '02 Oct 2026',
          premium: 69.5,
          projectedPl: 3190,
          marginImpact: -33480,
          payoffPoints: [
            { price: 7535, pl: -620 },
            { price: 7650, pl: 0 },
            { price: 7765, pl: 1650 }
          ]
        },
        {
          action: 'SELL',
          optionType: 'CALL',
          strike: 7765,
          expiry: '09 Oct 2026',
          premium: 85.0,
          projectedPl: 1650,
          marginImpact: 61820,
          payoffPoints: [
            { price: 7650, pl: 2160 },
            { price: 7765, pl: 1130 },
            { price: 7900, pl: -1650 }
          ]
        }
      ]
  },
  {
      name: 'Bull Put Spread',
      type: 'Directional Credit',
      strikes: '7535 / 7475',
      expectedPl: 4020,
      maxLoss: 8760,
      winProbability: 0.72,
      riskReward: 1.1,
      margin: 95300,
      score: 77,
      payoffPoints: [
        { price: 7420, pl: -8760 },
        { price: 7495, pl: 1030 },
        { price: 7535, pl: 4020 },
        { price: 7650, pl: 2320 },
        { price: 7725, pl: -2580 }
      ],
      legs: [
        {
          action: 'SELL',
          optionType: 'PUT',
          strike: 7535,
          expiry: '02 Oct 2026',
          premium: 54.1,
          projectedPl: 3710,
          marginImpact: 51520,
          payoffPoints: [
            { price: 7420, pl: -8240 },
            { price: 7535, pl: 720 },
            { price: 7630, pl: 2160 }
          ]
        },
        {
          action: 'BUY',
          optionType: 'PUT',
          strike: 7475,
          expiry: '02 Oct 2026',
          premium: 36.7,
          projectedPl: 310,
          marginImpact: -30910,
          payoffPoints: [
            { price: 7360, pl: 3090 },
            { price: 7475, pl: 0 },
            { price: 7575, pl: -1240 }
          ]
        }
      ]
  }
],
  greeks: {
    delta: 0.07,
    gamma: -0.01,
    theta: 2160,
    vega: -850,
    rho: 110
  }
};

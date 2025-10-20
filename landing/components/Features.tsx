'use client'

import * as React from 'react'
import {
  TrendingUp,
  Brain,
  Eye,
  Play,
  Briefcase,
  Shield,
  Zap,
  Cloud,
} from 'lucide-react'

const features = [
  {
    icon: TrendingUp,
    title: 'Market Data API',
    description: 'Real-time option chains, implied volatility, Greeks, and candlestick patterns. Access comprehensive market data for informed trading decisions.',
    color: 'text-primary-500',
    bgColor: 'bg-primary-500/10',
  },
  {
    icon: Brain,
    title: 'ML Prediction Engine',
    description: 'XGBoost models analyze market conditions and recommend optimal strategies with win probability and risk-reward scoring.',
    color: 'text-accent-500',
    bgColor: 'bg-accent-500/10',
  },
  {
    icon: Eye,
    title: 'SHAP Explainability',
    description: 'Understand exactly why models recommend specific strategies. Complete transparency and trust in every AI-driven decision.',
    color: 'text-secondary-500',
    bgColor: 'bg-secondary-500/10',
  },
  {
    icon: Play,
    title: 'Trading Simulator',
    description: 'Paper trade complex strategies like Iron Condor and Bull Call Spread. Run scenario analysis and backtesting without risking capital.',
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/10',
  },
  {
    icon: Briefcase,
    title: 'Portfolio Tracker',
    description: 'Real-time position tracking, PnL monitoring, and comprehensive trade history. Export your data to Cloud Storage anytime.',
    color: 'text-indigo-500',
    bgColor: 'bg-indigo-500/10',
  },
  {
    icon: Shield,
    title: 'Risk Analytics',
    description: 'Professional-grade metrics including VaR, CVaR, and Sharpe Ratio. Advanced risk management for serious traders.',
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
  },
  {
    icon: Zap,
    title: 'API Gateway',
    description: 'Secure RESTful endpoints with Firebase Authentication, rate limiting, and role-based access control (RBAC).',
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-500/10',
  },
  {
    icon: Cloud,
    title: 'Cloud-Native Architecture',
    description: 'Scalable microservices on Google Cloud with 99.9% uptime SLA. Built for performance and reliability at any scale.',
    color: 'text-cyan-500',
    bgColor: 'bg-cyan-500/10',
  },
]

export function Features() {
  return (
    <section id="features" className="py-24 px-4 sm:px-6 lg:px-8 bg-slate-50 dark:bg-slate-900/50">
      <div className="max-w-7xl mx-auto">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-4xl sm:text-5xl font-bold text-slate-900 dark:text-white mb-4">
            Everything You Need to{' '}
            <span className="bg-gradient-to-r from-primary-500 to-accent-500 bg-clip-text text-transparent">
              Master Options Trading
            </span>
          </h2>
          <p className="text-xl text-slate-600 dark:text-slate-300">
            A complete suite of tools designed for traders, quants, and developers
          </p>
        </div>

        {/* Features Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          {features.map((feature, index) => {
            const Icon = feature.icon
            return (
              <div
                key={index}
                className="group relative bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 hover:border-primary-300 dark:hover:border-primary-700 transition-all hover:shadow-xl hover:-translate-y-1"
              >
                {/* Icon */}
                <div className={`inline-flex items-center justify-center w-12 h-12 rounded-lg ${feature.bgColor} mb-4`}>
                  <Icon className={`h-6 w-6 ${feature.color}`} />
                </div>

                {/* Title */}
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
                  {feature.title}
                </h3>

                {/* Description */}
                <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed">
                  {feature.description}
                </p>

                {/* Hover Effect Border */}
                <div className="absolute inset-0 rounded-2xl bg-gradient-to-r from-primary-500 to-accent-500 opacity-0 group-hover:opacity-10 transition-opacity -z-10" />
              </div>
            )
          })}
        </div>

        {/* Bottom CTA */}
        <div className="text-center mt-16">
          <a
            href="#docs"
            className="inline-flex items-center text-primary-500 hover:text-primary-600 dark:text-primary-400 dark:hover:text-primary-300 font-semibold transition-colors"
          >
            Explore our documentation
            <svg className="ml-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </a>
        </div>
      </div>
    </section>
  )
}

'use client'

import * as React from 'react'
import { Database, Brain, ListChecks, Zap } from 'lucide-react'

const steps = [
  {
    icon: Database,
    number: '01',
    title: 'Ingest Market Data',
    description: 'Access real-time option chains, implied volatility, Greeks, candlestick patterns, and sentiment indicators from multiple sources.',
    color: 'from-primary-500 to-primary-600',
  },
  {
    icon: Brain,
    number: '02',
    title: 'AI Analysis',
    description: 'Our ML models perform volatility, technical, and sentiment analysis. XGBoost algorithms score each potential strategy.',
    color: 'from-accent-500 to-accent-600',
  },
  {
    icon: ListChecks,
    number: '03',
    title: 'Strategy Recommendations',
    description: 'Receive ranked strategies by win probability and risk-reward ratio. SHAP explanations provide full transparency.',
    color: 'from-secondary-500 to-secondary-600',
  },
  {
    icon: Zap,
    number: '04',
    title: 'Simulate & Execute',
    description: 'Paper trade or backtest strategies in real-time. Track portfolio performance with comprehensive risk metrics.',
    color: 'from-blue-500 to-cyan-500',
  },
]

export function HowItWorks() {
  return (
    <section className="py-24 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-20">
          <h2 className="text-4xl sm:text-5xl font-bold text-slate-900 dark:text-white mb-4">
            From Data to Decision{' '}
            <span className="bg-gradient-to-r from-primary-500 to-accent-500 bg-clip-text text-transparent">
              in Seconds
            </span>
          </h2>
          <p className="text-xl text-slate-600 dark:text-slate-300">
            Our intelligent workflow transforms raw market data into actionable trading strategies
          </p>
        </div>

        {/* Steps */}
        <div className="relative">
          {/* Connecting Line (Desktop) */}
          <div className="hidden lg:block absolute top-16 left-0 right-0 h-0.5 bg-gradient-to-r from-primary-200 via-accent-200 to-secondary-200 dark:from-primary-900 dark:via-accent-900 dark:to-secondary-900" />

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8 relative">
            {steps.map((step, index) => {
              const Icon = step.icon
              return (
                <div key={index} className="relative">
                  {/* Card */}
                  <div className="bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 hover:border-primary-300 dark:hover:border-primary-700 transition-all hover:shadow-xl group">
                    {/* Number Badge */}
                    <div className={`inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br ${step.color} text-white text-xl font-bold mb-6 relative z-10`}>
                      {step.number}
                    </div>

                    {/* Icon */}
                    <div className="flex items-center space-x-3 mb-4">
                      <Icon className="h-6 w-6 text-primary-500" />
                      <h3 className="text-xl font-semibold text-slate-900 dark:text-white">
                        {step.title}
                      </h3>
                    </div>

                    {/* Description */}
                    <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                      {step.description}
                    </p>

                    {/* Hover Gradient */}
                    <div className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${step.color} opacity-0 group-hover:opacity-5 transition-opacity -z-10`} />
                  </div>

                  {/* Arrow (Mobile) */}
                  {index < steps.length - 1 && (
                    <div className="flex justify-center my-4 lg:hidden">
                      <svg className="h-8 w-8 text-primary-300 dark:text-primary-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                      </svg>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Bottom Stats */}
        <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="text-center p-6 bg-slate-50 dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-800">
            <div className="text-3xl font-bold text-primary-500 mb-2">
              &lt; 2s
            </div>
            <div className="text-slate-600 dark:text-slate-400">
              Average prediction latency
            </div>
          </div>
          <div className="text-center p-6 bg-slate-50 dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-800">
            <div className="text-3xl font-bold text-accent-500 mb-2">
              10+
            </div>
            <div className="text-slate-600 dark:text-slate-400">
              Trading strategies supported
            </div>
          </div>
          <div className="text-center p-6 bg-slate-50 dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-800">
            <div className="text-3xl font-bold text-secondary-500 mb-2">
              24/7
            </div>
            <div className="text-slate-600 dark:text-slate-400">
              Real-time market monitoring
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

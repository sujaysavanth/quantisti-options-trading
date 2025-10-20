'use client'

import * as React from 'react'
import { Check, X, Sparkles } from 'lucide-react'

const plans = [
  {
    name: 'Basic',
    price: 'Free',
    period: 'forever',
    description: 'Perfect for getting started with options trading',
    features: [
      { name: 'Market Data Access', included: true },
      { name: 'Basic Portfolio Tracking', included: true },
      { name: 'Run Simulations', included: true },
      { name: 'Basic Stats & Analytics', included: true },
      { name: '100 API calls/min', included: true },
      { name: 'ML Predictions', included: false },
      { name: 'SHAP Explanations', included: false },
      { name: 'Export Data', included: false },
      { name: 'Advanced Risk Metrics', included: false },
    ],
    cta: 'Start Free',
    highlighted: false,
  },
  {
    name: 'Premium',
    price: '$49',
    period: '/month',
    description: 'For serious traders who need advanced features',
    features: [
      { name: 'Everything in Basic', included: true },
      { name: 'ML Predictions', included: true },
      { name: 'SHAP Explainability', included: true },
      { name: 'Export Simulations', included: true },
      { name: 'Advanced Risk Metrics', included: true },
      { name: 'VaR, CVaR, Sharpe Ratio', included: true },
      { name: '1,000 API calls/min', included: true },
      { name: 'Priority Support', included: true },
      { name: 'Custom Strategies', included: true },
    ],
    cta: 'Start 14-Day Trial',
    highlighted: true,
    badge: 'Most Popular',
  },
  {
    name: 'Admin',
    price: 'Custom',
    period: 'pricing',
    description: 'Enterprise-grade for teams and organizations',
    features: [
      { name: 'Everything in Premium', included: true },
      { name: 'User Management', included: true },
      { name: 'Audit Logs', included: true },
      { name: 'Admin Dashboard', included: true },
      { name: 'Priority Support', included: true },
      { name: 'White-label Options', included: true },
      { name: 'Unlimited API calls', included: true },
      { name: 'Dedicated Infrastructure', included: true },
      { name: 'SLA Guarantees', included: true },
    ],
    cta: 'Contact Sales',
    highlighted: false,
  },
]

export function Pricing() {
  return (
    <section id="pricing" className="py-24 px-4 sm:px-6 lg:px-8 bg-slate-50 dark:bg-slate-900/50">
      <div className="max-w-7xl mx-auto">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-4xl sm:text-5xl font-bold text-slate-900 dark:text-white mb-4">
            Choose Your{' '}
            <span className="bg-gradient-to-r from-primary-500 to-accent-500 bg-clip-text text-transparent">
              Trading Tier
            </span>
          </h2>
          <p className="text-xl text-slate-600 dark:text-slate-300">
            Flexible plans that scale with your trading needs
          </p>
        </div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {plans.map((plan, index) => (
            <div
              key={index}
              className={`relative bg-white dark:bg-slate-900 rounded-2xl p-8 border-2 transition-all ${
                plan.highlighted
                  ? 'border-primary-500 shadow-2xl shadow-primary-500/20 scale-105'
                  : 'border-slate-200 dark:border-slate-800 hover:border-primary-300 dark:hover:border-primary-700'
              }`}
            >
              {/* Badge */}
              {plan.badge && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <div className="inline-flex items-center space-x-1 px-4 py-1.5 bg-gradient-to-r from-primary-500 to-accent-500 text-white text-sm font-semibold rounded-full">
                    <Sparkles className="h-4 w-4" />
                    <span>{plan.badge}</span>
                  </div>
                </div>
              )}

              {/* Plan Name */}
              <div className="text-center mb-6">
                <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
                  {plan.name}
                </h3>
                <p className="text-slate-600 dark:text-slate-400 text-sm">
                  {plan.description}
                </p>
              </div>

              {/* Price */}
              <div className="text-center mb-8">
                <div className="flex items-baseline justify-center">
                  <span className="text-5xl font-bold text-slate-900 dark:text-white">
                    {plan.price}
                  </span>
                  <span className="ml-2 text-slate-600 dark:text-slate-400">
                    {plan.period}
                  </span>
                </div>
              </div>

              {/* CTA Button */}
              <a
                href={plan.name === 'Admin' ? '#contact' : '#signup'}
                className={`block w-full text-center px-6 py-3 rounded-lg font-semibold transition-all mb-8 ${
                  plan.highlighted
                    ? 'bg-primary-500 hover:bg-primary-600 text-white shadow-lg shadow-primary-500/30'
                    : 'border-2 border-slate-300 dark:border-slate-600 hover:border-primary-500 dark:hover:border-primary-500 text-slate-700 dark:text-slate-300'
                }`}
              >
                {plan.cta}
              </a>

              {/* Features List */}
              <div className="space-y-3">
                {plan.features.map((feature, featureIndex) => (
                  <div key={featureIndex} className="flex items-start space-x-3">
                    {feature.included ? (
                      <Check className="h-5 w-5 text-secondary-500 flex-shrink-0 mt-0.5" />
                    ) : (
                      <X className="h-5 w-5 text-slate-300 dark:text-slate-600 flex-shrink-0 mt-0.5" />
                    )}
                    <span
                      className={`text-sm ${
                        feature.included
                          ? 'text-slate-700 dark:text-slate-300'
                          : 'text-slate-400 dark:text-slate-600 line-through'
                      }`}
                    >
                      {feature.name}
                    </span>
                  </div>
                ))}
              </div>

              {/* Highlight Gradient */}
              {plan.highlighted && (
                <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-primary-500/10 to-accent-500/10 -z-10" />
              )}
            </div>
          ))}
        </div>

        {/* FAQ Link */}
        <div className="text-center mt-12">
          <p className="text-slate-600 dark:text-slate-400">
            Have questions?{' '}
            <a href="#faq" className="text-primary-500 hover:text-primary-600 dark:text-primary-400 dark:hover:text-primary-300 font-semibold">
              View our FAQ
            </a>
            {' '}or{' '}
            <a href="#contact" className="text-primary-500 hover:text-primary-600 dark:text-primary-400 dark:hover:text-primary-300 font-semibold">
              contact sales
            </a>
          </p>
        </div>
      </div>
    </section>
  )
}

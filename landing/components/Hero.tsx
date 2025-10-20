'use client'

import * as React from 'react'
import { ArrowRight, Shield, Rocket, BarChart3, Sparkles } from 'lucide-react'

export function Hero() {
  return (
    <section className="relative pt-32 pb-20 px-4 sm:px-6 lg:px-8 overflow-hidden">
      {/* Background Gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary-50 via-white to-accent-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 -z-10" />

      {/* Grid Pattern */}
      <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10 -z-10" />

      <div className="max-w-7xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          {/* Left Column - Text Content */}
          <div className="space-y-8">
            {/* Badge */}
            <div className="inline-flex items-center space-x-2 px-4 py-2 rounded-full bg-primary-100 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800">
              <Sparkles className="h-4 w-4 text-primary-500" />
              <span className="text-sm font-medium text-primary-700 dark:text-primary-300">
                ML-Powered Options Trading Platform
              </span>
            </div>

            {/* Headline */}
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold text-slate-900 dark:text-white leading-tight">
              Intelligent Options Trading,{' '}
              <span className="bg-gradient-to-r from-primary-500 to-accent-500 bg-clip-text text-transparent">
                Powered by ML
              </span>
            </h1>

            {/* Subheadline */}
            <p className="text-xl text-slate-600 dark:text-slate-300 leading-relaxed max-w-2xl">
              Simulate, analyze, and optimize your options strategies with ML-powered predictions,
              SHAP explainability, and comprehensive risk analytics.
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-4">
              <a
                href="#signup"
                className="inline-flex items-center justify-center px-8 py-4 bg-primary-500 hover:bg-primary-600 text-white rounded-lg font-semibold transition-colors shadow-lg shadow-primary-500/30 group"
              >
                Start Free Trial
                <ArrowRight className="ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
              </a>
              <a
                href="#demo"
                className="inline-flex items-center justify-center px-8 py-4 border-2 border-slate-300 dark:border-slate-600 hover:border-primary-500 dark:hover:border-primary-500 text-slate-700 dark:text-slate-300 rounded-lg font-semibold transition-colors"
              >
                View Live Demo
              </a>
            </div>

            {/* Trust Indicators */}
            <div className="flex flex-wrap gap-6 pt-4">
              <div className="flex items-center space-x-2 text-slate-600 dark:text-slate-400">
                <Shield className="h-5 w-5 text-secondary-500" />
                <span className="text-sm font-medium">Enterprise Security</span>
              </div>
              <div className="flex items-center space-x-2 text-slate-600 dark:text-slate-400">
                <Rocket className="h-5 w-5 text-primary-500" />
                <span className="text-sm font-medium">Cloud-Native</span>
              </div>
              <div className="flex items-center space-x-2 text-slate-600 dark:text-slate-400">
                <BarChart3 className="h-5 w-5 text-accent-500" />
                <span className="text-sm font-medium">Real-time Analytics</span>
              </div>
            </div>
          </div>

          {/* Right Column - Visual/Mockup */}
          <div className="relative lg:h-[600px] hidden lg:block">
            {/* Floating Cards */}
            <div className="absolute top-0 right-0 w-80 bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-700 p-6 transform rotate-3 hover:rotate-0 transition-transform">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-slate-900 dark:text-white">ML Prediction</h3>
                  <span className="px-2 py-1 bg-secondary-100 dark:bg-secondary-900/30 text-secondary-700 dark:text-secondary-300 text-xs rounded-full font-medium">
                    High Confidence
                  </span>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-600 dark:text-slate-400">Strategy</span>
                    <span className="font-medium text-slate-900 dark:text-white">Iron Condor</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-600 dark:text-slate-400">Win Probability</span>
                    <span className="font-medium text-secondary-600 dark:text-secondary-400">78%</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-600 dark:text-slate-400">Risk/Reward</span>
                    <span className="font-medium text-slate-900 dark:text-white">1:3.2</span>
                  </div>
                </div>
                <div className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div className="h-full w-4/5 bg-gradient-to-r from-primary-500 to-accent-500 rounded-full" />
                </div>
              </div>
            </div>

            <div className="absolute bottom-20 left-0 w-72 bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-700 p-6 transform -rotate-3 hover:rotate-0 transition-transform">
              <div className="space-y-4">
                <h3 className="font-semibold text-slate-900 dark:text-white">Risk Metrics</h3>
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-slate-600 dark:text-slate-400">VaR (95%)</span>
                      <span className="font-medium text-slate-900 dark:text-white">$2,450</span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                      <div className="h-full w-2/3 bg-accent-500 rounded-full" />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-slate-600 dark:text-slate-400">Sharpe Ratio</span>
                      <span className="font-medium text-secondary-600 dark:text-secondary-400">2.34</span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                      <div className="h-full w-4/5 bg-secondary-500 rounded-full" />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-slate-600 dark:text-slate-400">Portfolio Beta</span>
                      <span className="font-medium text-slate-900 dark:text-white">0.87</span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                      <div className="h-full w-3/4 bg-primary-500 rounded-full" />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Decorative Elements */}
            <div className="absolute top-1/4 right-1/4 w-20 h-20 bg-primary-500/10 rounded-full blur-2xl" />
            <div className="absolute bottom-1/4 left-1/4 w-32 h-32 bg-accent-500/10 rounded-full blur-2xl" />
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mt-20 pt-12 border-t border-slate-200 dark:border-slate-800">
          <div className="text-center">
            <div className="text-4xl font-bold text-slate-900 dark:text-white">7</div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">Microservices</div>
          </div>
          <div className="text-center">
            <div className="text-4xl font-bold text-slate-900 dark:text-white">99.9%</div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">Uptime SLA</div>
          </div>
          <div className="text-center">
            <div className="text-4xl font-bold text-slate-900 dark:text-white">AI/ML</div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">Powered</div>
          </div>
          <div className="text-center">
            <div className="text-4xl font-bold text-slate-900 dark:text-white">RBAC</div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">Security</div>
          </div>
        </div>
      </div>
    </section>
  )
}

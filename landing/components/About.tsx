'use client'

import * as React from 'react'
import { Server, Brain, Shield, Cloud } from 'lucide-react'

const stats = [
  {
    icon: Server,
    value: '7',
    label: 'Microservices',
    description: 'Modular, scalable architecture',
  },
  {
    icon: Brain,
    value: 'XGBoost',
    label: '+ SHAP',
    description: 'Transparent AI predictions',
  },
  {
    icon: Shield,
    value: 'Enterprise',
    label: 'Security',
    description: 'Firebase Auth + RBAC',
  },
  {
    icon: Cloud,
    value: '99.9%',
    label: 'Uptime SLA',
    description: 'Google Cloud powered',
  },
]

const techStack = [
  'React.js',
  'Next.js',
  'Python',
  'FastAPI',
  'XGBoost',
  'Google Cloud',
  'PostgreSQL',
  'Docker',
  'Terraform',
  'Firebase',
]

export function About() {
  return (
    <section id="about" className="py-24 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Left Column - Text Content */}
          <div className="space-y-6">
            <h2 className="text-4xl sm:text-5xl font-bold text-slate-900 dark:text-white">
              Built by Traders,{' '}
              <span className="bg-gradient-to-r from-primary-500 to-accent-500 bg-clip-text text-transparent">
                for Traders
              </span>
            </h2>

            <div className="prose prose-lg dark:prose-invert">
              <p className="text-lg text-slate-600 dark:text-slate-300 leading-relaxed">
                Quantisti is a cutting-edge options trading platform that combines institutional-grade
                analytics with modern machine learning. Our mission is to democratize sophisticated
                trading strategies through transparent, explainable AI.
              </p>

              <p className="text-lg text-slate-600 dark:text-slate-300 leading-relaxed">
                Whether you're a retail trader learning the ropes or a quant building complex strategies,
                Quantisti provides the tools, data, and insights you need to trade with confidence.
              </p>
            </div>

            {/* Key Principles */}
            <div className="space-y-4 pt-4">
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-secondary-500/20 flex items-center justify-center mt-1">
                  <div className="w-2 h-2 rounded-full bg-secondary-500" />
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900 dark:text-white">Transparency First</h4>
                  <p className="text-slate-600 dark:text-slate-400">
                    Every ML prediction comes with SHAP explanations so you understand the "why"
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary-500/20 flex items-center justify-center mt-1">
                  <div className="w-2 h-2 rounded-full bg-primary-500" />
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900 dark:text-white">Enterprise-Grade Security</h4>
                  <p className="text-slate-600 dark:text-slate-400">
                    Role-based access control, audit logs, and Firebase authentication
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-accent-500/20 flex items-center justify-center mt-1">
                  <div className="w-2 h-2 rounded-full bg-accent-500" />
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900 dark:text-white">Cloud-Native Scale</h4>
                  <p className="text-slate-600 dark:text-slate-400">
                    Built on Google Cloud with microservices architecture for unlimited scalability
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column - Stats & Tech Stack */}
          <div className="space-y-8">
            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-6">
              {stats.map((stat, index) => {
                const Icon = stat.icon
                return (
                  <div
                    key={index}
                    className="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 rounded-2xl p-6 border border-slate-200 dark:border-slate-700"
                  >
                    <Icon className="h-8 w-8 text-primary-500 mb-3" />
                    <div className="text-3xl font-bold text-slate-900 dark:text-white mb-1">
                      {stat.value}
                    </div>
                    <div className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1">
                      {stat.label}
                    </div>
                    <div className="text-xs text-slate-600 dark:text-slate-400">
                      {stat.description}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Tech Stack */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl p-8 border border-slate-200 dark:border-slate-800">
              <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-6">
                Powered by Industry-Leading Technologies
              </h3>
              <div className="flex flex-wrap gap-3">
                {techStack.map((tech, index) => (
                  <div
                    key={index}
                    className="px-4 py-2 bg-slate-100 dark:bg-slate-800 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:border-primary-300 dark:hover:border-primary-700 transition-colors"
                  >
                    {tech}
                  </div>
                ))}
              </div>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-6">
                Modern stack, battle-tested architecture, production-ready from day one
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

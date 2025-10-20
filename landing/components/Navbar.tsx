'use client'

import * as React from 'react'
import { Menu, X, ChevronDown, TrendingUp } from 'lucide-react'
import { ThemeToggle } from './ThemeToggle'

const services = [
  { name: 'Market Data API', href: '#features', description: 'Real-time options data & Greeks' },
  { name: 'ML Prediction Engine', href: '#features', description: 'XGBoost-powered predictions' },
  { name: 'Explainability (SHAP)', href: '#features', description: 'Transparent AI insights' },
  { name: 'Trading Simulator', href: '#features', description: 'Paper trade strategies' },
  { name: 'Portfolio Tracker', href: '#features', description: 'Real-time PnL tracking' },
  { name: 'Risk Analytics', href: '#features', description: 'VaR, CVaR, Sharpe Ratio' },
  { name: 'API Gateway', href: '#features', description: 'Secure API access' },
]

export function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false)
  const [servicesOpen, setServicesOpen] = React.useState(false)

  return (
    <nav className="fixed top-0 w-full z-50 bg-white/80 dark:bg-slate-950/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex items-center space-x-2">
            <TrendingUp className="h-8 w-8 text-primary-500" />
            <span className="text-2xl font-bold bg-gradient-to-r from-primary-500 to-accent-500 bg-clip-text text-transparent">
              Quantisti
            </span>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-8">
            {/* Services Dropdown */}
            <div className="relative">
              <button
                onMouseEnter={() => setServicesOpen(true)}
                onMouseLeave={() => setServicesOpen(false)}
                className="flex items-center space-x-1 text-slate-700 dark:text-slate-300 hover:text-primary-500 dark:hover:text-primary-400 transition-colors"
              >
                <span className="font-medium">Services</span>
                <ChevronDown className="h-4 w-4" />
              </button>

              {/* Dropdown Menu */}
              {servicesOpen && (
                <div
                  onMouseEnter={() => setServicesOpen(true)}
                  onMouseLeave={() => setServicesOpen(false)}
                  className="absolute left-0 mt-2 w-80 bg-white dark:bg-slate-900 rounded-lg shadow-xl border border-slate-200 dark:border-slate-700 py-2"
                >
                  {services.map((service) => (
                    <a
                      key={service.name}
                      href={service.href}
                      className="block px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                    >
                      <div className="font-medium text-slate-900 dark:text-slate-100">
                        {service.name}
                      </div>
                      <div className="text-sm text-slate-600 dark:text-slate-400">
                        {service.description}
                      </div>
                    </a>
                  ))}
                </div>
              )}
            </div>

            <a href="#features" className="text-slate-700 dark:text-slate-300 hover:text-primary-500 dark:hover:text-primary-400 transition-colors font-medium">
              Features
            </a>
            <a href="#pricing" className="text-slate-700 dark:text-slate-300 hover:text-primary-500 dark:hover:text-primary-400 transition-colors font-medium">
              Pricing
            </a>
            <a href="#about" className="text-slate-700 dark:text-slate-300 hover:text-primary-500 dark:hover:text-primary-400 transition-colors font-medium">
              About
            </a>
            <a href="#docs" className="text-slate-700 dark:text-slate-300 hover:text-primary-500 dark:hover:text-primary-400 transition-colors font-medium">
              Docs
            </a>
          </div>

          {/* Right Side - Theme Toggle & CTA Buttons */}
          <div className="hidden md:flex items-center space-x-4">
            <ThemeToggle />
            <a
              href="#signin"
              className="px-4 py-2 text-slate-700 dark:text-slate-300 hover:text-primary-500 dark:hover:text-primary-400 transition-colors font-medium"
            >
              Sign In
            </a>
            <a
              href="#signup"
              className="px-6 py-2 bg-primary-500 hover:bg-primary-600 text-white rounded-lg font-medium transition-colors shadow-lg shadow-primary-500/30"
            >
              Get Started
            </a>
          </div>

          {/* Mobile Menu Button */}
          <div className="md:hidden flex items-center space-x-2">
            <ThemeToggle />
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden py-4 border-t border-slate-200 dark:border-slate-800">
            <div className="flex flex-col space-y-4">
              <div>
                <button
                  onClick={() => setServicesOpen(!servicesOpen)}
                  className="flex items-center justify-between w-full text-slate-700 dark:text-slate-300 font-medium"
                >
                  <span>Services</span>
                  <ChevronDown className={`h-4 w-4 transition-transform ${servicesOpen ? 'rotate-180' : ''}`} />
                </button>
                {servicesOpen && (
                  <div className="mt-2 ml-4 space-y-2">
                    {services.map((service) => (
                      <a
                        key={service.name}
                        href={service.href}
                        className="block py-2 text-sm text-slate-600 dark:text-slate-400 hover:text-primary-500"
                      >
                        {service.name}
                      </a>
                    ))}
                  </div>
                )}
              </div>
              <a href="#features" className="text-slate-700 dark:text-slate-300 font-medium">Features</a>
              <a href="#pricing" className="text-slate-700 dark:text-slate-300 font-medium">Pricing</a>
              <a href="#about" className="text-slate-700 dark:text-slate-300 font-medium">About</a>
              <a href="#docs" className="text-slate-700 dark:text-slate-300 font-medium">Docs</a>
              <div className="pt-4 border-t border-slate-200 dark:border-slate-800 space-y-2">
                <a
                  href="#signin"
                  className="block w-full px-4 py-2 text-center border border-slate-300 dark:border-slate-600 rounded-lg text-slate-700 dark:text-slate-300 font-medium"
                >
                  Sign In
                </a>
                <a
                  href="#signup"
                  className="block w-full px-4 py-2 text-center bg-primary-500 hover:bg-primary-600 text-white rounded-lg font-medium"
                >
                  Get Started
                </a>
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  )
}

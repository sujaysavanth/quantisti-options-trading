import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from '@/components/Providers'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' })

export const metadata: Metadata = {
  title: 'Quantisti — Options, explained.',
  description:
    'Predict the week’s S&P 500 range, pick the SPX options strategy, and see exactly why. ML signals with SHAP explanations, Black-Scholes pricing, backtests and paper trading.',
  keywords: ['options trading', 'SPX', 'S&P 500', '0DTE', 'trading simulator', 'machine learning', 'SHAP', 'XGBoost', 'Black-Scholes'],
  authors: [{ name: 'Sujay Govindappa Rajashekar', url: 'https://github.com/sujaysavanth' }],
  openGraph: {
    title: 'Quantisti — Options, explained.',
    description: 'Predict the week’s range. Pick the strategy. See exactly why.',
    type: 'website',
  },
}

export const viewport: Viewport = {
  themeColor: '#000000',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}

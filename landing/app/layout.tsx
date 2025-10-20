import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { ThemeProvider } from '@/components/ThemeProvider'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Quantisti - Intelligent Options Trading Platform',
  description: 'Simulate, analyze, and optimize your options strategies with ML-powered predictions, SHAP explainability, and comprehensive risk analytics.',
  keywords: ['options trading', 'machine learning', 'trading simulator', 'portfolio tracker', 'risk analytics', 'SHAP', 'XGBoost'],
  authors: [{ name: 'Quantisti' }],
  openGraph: {
    title: 'Quantisti - Intelligent Options Trading Platform',
    description: 'ML-powered options trading with explainability and risk analytics',
    type: 'website',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className={inter.className}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  )
}

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import classNames from 'classnames';
import { ThemeToggle } from '@/components/ThemeToggle';
import { useLiveQuote } from '@/components/LiveQuoteProvider';
import { feedLabel } from '@/data/live';

const LINKS = [
  { href: '/', label: 'Strategies' },
  { href: '/chain', label: 'Option Chain' },
  { href: '/paper', label: 'Paper' }
];

export function NavBar() {
  const pathname = usePathname();
  const { quote, status } = useLiveQuote();

  return (
    <nav className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <span className="font-semibold tracking-tight">Quantisti</span>
        <div className="flex gap-1">
          {LINKS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={classNames(
                'rounded-full px-3 py-1.5 text-sm transition-colors',
                pathname === href
                  ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                  : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
              )}
            >
              {label}
            </Link>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-3">
          {status === 'live' && quote ? (
            <span
              className="inline-flex items-center gap-2 rounded-full border border-amber-300/60 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300"
              title="Free data source: option quotes lag the market"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" aria-hidden="true" />
              <span className="tabular-nums">SPX {quote.last_price.toLocaleString('en-US', { maximumFractionDigits: 2 })}</span>
              <span className="hidden sm:inline">· {feedLabel(quote)}</span>
            </span>
          ) : status === 'waiting' ? (
            <span className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
              Waiting for market data
            </span>
          ) : null}
          <ThemeToggle />
        </div>
      </div>
    </nav>
  );
}

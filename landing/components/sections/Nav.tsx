'use client'

import { Menu, X } from 'lucide-react'
import { useState } from 'react'
import { PillButton } from '@/components/ui/Buttons'
import { DASHBOARD_URL, HAS_DASHBOARD } from '@/lib/links'

const links = [
  { href: '#range', label: 'Prediction' },
  { href: '#chain', label: 'Chain' },
  { href: '#strategies', label: 'Strategies' },
  { href: '#signals', label: 'Signals' },
  { href: '#risk', label: 'Risk' },
  { href: '#tech', label: 'Tech' },
]

export function Nav() {
  const [open, setOpen] = useState(false)

  return (
    <header className="glass fixed inset-x-0 top-0 z-50 text-paper">
      <nav aria-label="Primary" className="mx-auto flex h-12 max-w-[1024px] items-center justify-between px-4 sm:px-6">
        <a href="#top" className="text-[15px] font-semibold tracking-tight">
          Quantisti
        </a>

        <ul className="hidden items-center gap-8 md:flex">
          {links.map((l) => (
            <li key={l.href}>
              <a href={l.href} className="text-xs text-paper/80 transition-colors hover:text-paper">
                {l.label}
              </a>
            </li>
          ))}
        </ul>

        <div className="flex items-center gap-3">
          <PillButton href={DASHBOARD_URL} size="sm">
            {HAS_DASHBOARD ? 'Open dashboard' : 'View code'}
          </PillButton>
          <button
            type="button"
            className="-mr-2 p-2 text-paper/80 md:hidden"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
            aria-controls="mobile-menu"
            onClick={() => setOpen((o) => !o)}
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </nav>

      {open && (
        <ul id="mobile-menu" className="border-t border-white/10 px-6 pb-6 pt-2 md:hidden">
          {links.map((l) => (
            <li key={l.href}>
              <a href={l.href} onClick={() => setOpen(false)} className="block py-3 text-2xl font-semibold text-paper">
                {l.label}
              </a>
            </li>
          ))}
        </ul>
      )}
    </header>
  )
}

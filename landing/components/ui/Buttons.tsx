import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'

interface LinkProps {
  href: string
  children: ReactNode
  className?: string
  external?: boolean
}

function externalProps(href: string, external?: boolean) {
  return external ?? href.startsWith('http') ? { target: '_blank', rel: 'noopener noreferrer' } : {}
}

export function PillButton({ href, children, className = '', external, size = 'lg' }: LinkProps & { size?: 'sm' | 'lg' }) {
  const sizing = size === 'lg' ? 'px-6 py-3 text-[17px]' : 'px-3 py-1 text-xs'
  return (
    <a
      href={href}
      {...externalProps(href, external)}
      className={`inline-flex items-center justify-center rounded-full bg-[#0071e3] font-normal text-white transition-colors hover:bg-[#0077ed] ${sizing} ${className}`}
    >
      {children}
    </a>
  )
}

export function TextLink({ href, children, className = '', external }: LinkProps) {
  return (
    <a
      href={href}
      {...externalProps(href, external)}
      className={`group inline-flex items-center text-[17px] text-link hover:underline ${className}`}
    >
      {children}
      <ChevronRight aria-hidden className="ml-0.5 h-4 w-4 transition-transform group-hover:translate-x-0.5" />
    </a>
  )
}

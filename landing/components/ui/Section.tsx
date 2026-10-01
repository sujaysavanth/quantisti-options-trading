import type { ReactNode } from 'react'

export type Tone = 'dark' | 'light'

interface SectionProps {
  id?: string
  tone: Tone
  className?: string
  /** Set false for sticky scenes, which manage their own height. */
  padded?: boolean
  children: ReactNode
  'aria-label'?: string
}

export function Section({ id, tone, className = '', padded = true, children, ...rest }: SectionProps) {
  return (
    <section
      id={id}
      className={`tone-${tone} relative scroll-mt-12 ${padded ? 'px-4 py-24 sm:px-6 md:py-40' : ''} ${className}`}
      {...rest}
    >
      {children}
    </section>
  )
}

export function Eyebrow({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <p className={`text-eyebrow text-muted ${className}`}>{children}</p>
}

export function Headline({ children, className = '', as: Tag = 'h2' }: { children: ReactNode; className?: string; as?: 'h1' | 'h2' | 'h3' }) {
  return <Tag className={`text-headline text-balance ${className}`}>{children}</Tag>
}

export function Lede({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <p className={`text-lede text-balance text-muted ${className}`}>{children}</p>
}

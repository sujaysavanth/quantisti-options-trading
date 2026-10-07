import { AUTHOR_URL, GITHUB_URL } from '@/lib/links'

export function Footer() {
  return (
    <footer className="bg-paper px-4 pb-10 pt-8 text-xs text-muted sm:px-6">
      <div className="mx-auto max-w-[980px]">
        <div className="space-y-3 border-b border-black/10 pb-6 leading-relaxed">
          <p>
            Quantisti is a simulation and research project. Nothing on this page or in the platform is investment advice, and no real orders
            are placed. Options involve substantial risk.
          </p>
          <p>
            Figures shown on this page are illustrative. Option values are computed with Black-Scholes from sample market parameters; historical
            index data is sourced from Yahoo Finance, VIX from CBOE and rates from FRED.
          </p>
        </div>
        <div className="flex flex-col gap-3 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p>© 2026 Sujay Govindappa Rajashekar. MIT License.</p>
          <ul className="flex gap-6">
            <li>
              <a className="text-ink/80 hover:underline" href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
                Source
              </a>
            </li>
            <li>
              <a className="text-ink/80 hover:underline" href={AUTHOR_URL} target="_blank" rel="noopener noreferrer">
                Author
              </a>
            </li>
            <li>
              <a className="text-ink/80 hover:underline" href="#top">
                Back to top
              </a>
            </li>
          </ul>
        </div>
      </div>
    </footer>
  )
}

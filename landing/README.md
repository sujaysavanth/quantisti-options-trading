# Quantisti Landing Page

Apple-style product page for the Quantisti options trading platform. Next.js 15 (App Router), React 19, Tailwind CSS 3 and Motion.

Design direction and section plan: [`../docs/landing-redesign-plan.md`](../docs/landing-redesign-plan.md).

## Develop

```bash
npm install
npm run dev      # http://localhost:3000
npm run build
npm run lint
```

Optional: set `NEXT_PUBLIC_DASHBOARD_URL` to the deployed strategy dashboard. When it is set, the primary buttons read "Open dashboard"; otherwise they link to the GitHub repository.

## Sections

Nav → Hero (interactive iron-condor payoff) → Weekly range prediction (scroll-pinned) → Option chain → Strategy recommendations (scroll-pinned, payoff morphs between strategies) → SHAP explanation → Risk analytics → How it works (scroll-pinned pipeline) → Highlights bento → Tech specs → Final CTA → Footer.

## How the numbers work

`data/showcase.ts` holds one sample SPX market (spot, IV, rate, days to expiry). Premiums, payoffs, Greeks, breakevens and probability of profit are computed from it with Black-Scholes (`lib/blackScholes.ts`, `lib/payoff.ts`), so the figures on the page agree with each other. Price history and backtest returns come from a seeded random generator, so they're stable between builds. All of it is illustrative, as the footer states.

## Conventions

- Sections alternate `tone="dark"` / `tone="light"` via `components/ui/Section.tsx`; tone-dependent colours (`link`, `gain`, `loss`) are CSS variables set per tone.
- Green and red mean profit and loss only.
- Scroll-pinned scenes use `components/ui/StickyScene.tsx`, which passes a 0 → 1 progress value to its child.
- Animate only `transform`, `opacity` and SVG path data. `Providers.tsx` sets `reducedMotion="user"`.
- Charts are hand-built SVG, with text labels in HTML overlays so they aren't stretched.

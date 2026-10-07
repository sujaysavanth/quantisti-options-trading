# Landing Redesign Plan — Apple-style

Target: `landing/` (Next.js 15, React 19, Tailwind 3, lucide-react, next-themes).
Goal: portfolio showpiece. Sample/illustrative numbers are fine.

## 1. Current state → what changes

| Current | Problem vs. Apple style | New |
|---|---|---|
| `Hero.tsx` — two tilted floating cards, gradient text, badge, 3 trust icons, stats row | Busy; the product isn't shown; gradient text everywhere | Full-viewport black hero, one headline, live interactive SPX payoff curve as the "product shot" |
| `Features.tsx` — 8 icon cards, 8 different icon colors | Generic SaaS grid; colors compete | Replaced by 4 full-screen showcase sections + one bento grid with real UI crops |
| `HowItWorks.tsx` — 4 numbered cards | Static | Scroll-pinned pipeline that assembles as you scroll |
| `About.tsx` — text + stat cards + tech chips | Wordy | "Under the hood" spec table (Apple tech-specs style) |
| `Pricing.tsx` — 3 tiers | Apple product pages lead with the product, not tiers | Removed (see open decisions) |
| `CTA.tsx` — gradient + blobs + trust checks | Busy | Minimal black section: headline + one pill button |
| `Navbar.tsx` — services dropdown, theme toggle, 2 buttons | Heavy | 44px frosted bar: wordmark · 5 section links · one small pill CTA |
| `Footer.tsx` — 4 link columns of `#` placeholders | Dead links | Apple-style small-print footer: disclaimer, GitHub, author, license |
| `globals.css` `* { transition: ... }` | Transitions every element; janky | Remove |
| `bg-[url('/grid.svg')]` | `landing/public/` doesn't exist → 404 | Remove |
| Global dark/light toggle | Apple alternates section colors instead | Fixed section themes; drop toggle on landing |

## 2. New page flow

Content anchors on what the platform actually does: **SPX options** (daily expiries), ML range prediction, strategy recommendations, paper trading, risk.

1. **Nav** — `Quantisti` · Chain · Strategies · Signals · Risk · Tech · `[Open dashboard]`
2. **Hero** (black) — eyebrow "Quantisti"; headline **"Options, explained."**; sub "Predict the week's range. Pick the strategy. See exactly why."; `Open dashboard` pill + `View on GitHub ›`. Below: large payoff curve that draws in, with shaded profit/loss zones and a draggable spot marker updating P/L.
3. **Predicted range** (black, sticky 250vh) — SPX price line; as you scroll the ML-predicted weekly band (lower/upper, confidence) fades in, then the closing estimate dot lands. Big numbers: "±1.8% range · 72% confidence".
4. **Options chain** (light `#f5f5f7`) — "Every strike. At a glance." Chain table rises and scales into view; three callouts: Greeks, IV per expiry, PCR.
5. **Strategy recommendations** (black, sticky) — pinned payoff chart on the left; scrolling steps on the right cycle through Iron Condor → Bull Call Spread → Short Strangle; the curve morphs between shapes, win-probability / risk-reward numbers count to new values.
6. **Explainability** (light) — "The model shows its work." SHAP waterfall bars grow one by one (VIX, OI-PCR, trend, IV rank, …).
7. **Risk** (black) — return histogram with VaR/CVaR lines sliding in; Sharpe, Sortino, Max DD as huge numbers.
8. **How it works** (light, sticky) — pipeline: Yahoo/CBOE/FRED data → Market service → ML service → Simulator → Dashboard; nodes light up with scroll progress.
9. **Highlights bento** (black) — 6 tiles: payoff, Greeks, paper trading, backtests, SHAP, cloud-native.
10. **Under the hood** (light) — spec table: services, stack, data sources, model, deployment (Cloud Run, Terraform, GitHub Actions).
11. **Final CTA** (black) — "Trade the week, on paper." + pill.
12. **Footer** (light gray, 12px) — "Simulation only. Not investment advice." · GitHub · LinkedIn · © 2026 · MIT.

## 3. Design system (landing only)

- **Font**: `next/font` Inter (variable) as fallback behind `-apple-system, BlinkMacSystemFont` (SF appears on Apple devices; SF isn't licensed for self-hosting). `tabular-nums` on all figures.
- **Type scale**: hero 96/72/48px (xl/md/sm), section 64/48/36px, sub 24/21px, body 17px, footnote 12px; weight 600; tracking -0.02em on display sizes.
- **Colors (CSS vars)**: `--black #000`, `--ink #1d1d1f`, `--paper #f5f5f7`, `--muted #86868b`, `--link #2997ff` (on dark) / `#0066cc` (on light), `--gain #30d158`, `--loss #ff453a` (charts only).
- **Layout**: section padding 160px/96px (desktop/mobile); text max 980px, visuals max 1200px.
- **Shape**: cards/screens radius 28px, pill buttons, no borders; one soft shadow on floating UI shots only.
- **Glass**: nav `backdrop-blur-xl bg-black/70`, saturate 180%.
- Remove gradient text, multicolor icons, decorative blobs.

## 4. Motion

- Add `motion` (Motion for React). Scroll-linked: `useScroll({ target, offset })` + `useTransform`; reveals: `whileInView` fade + 24px rise, 0.6s, ease `[0.25,0.1,0.25,1]`, `once`.
- Sticky scenes: outer section `h-[250vh]`, inner `sticky top-0 h-screen`; progress 0→1 drives the scene.
- Chart draw: SVG `pathLength` 0→1; curve morph by interpolating payoff arrays sampled on a shared price grid (same x points → smooth tween).
- `useReducedMotion()` → render final states, no scroll transforms.
- Animate only `transform` / `opacity` / SVG path props.

## 5. Visual assets

- **Charts**: hand-built SVG components (payoff, range band, SHAP bars, histogram, pipeline) — crisp, themeable, animatable, tiny.
- **Payoff math**: `landing/lib/payoff.ts` — expiry payoff for multi-leg strategies on a price grid (reuses the leg shape from `services/strategy-dashboard/data/mockDashboard.ts`).
- **Sample data**: `landing/data/showcase.ts` — SPX spot, predicted range, 3 strategies with legs, Greeks, SHAP values, return series. Illustrative values.
- **UI shots**: real screenshots of `services/strategy-dashboard` (`/` and `/paper`) captured at 2x into `landing/public/shots/` for the chain/bento sections.
- **3D (optional, phase 5)**: an IV surface or P/L-over-time surface as the hero backdrop. Two routes:
  - `@react-three/fiber` — live, rotatable in-browser, no extra tooling. **Preferred.**
  - Blender — pre-rendered image sequence scrubbed on scroll (the literal Apple technique). Highest polish, larger payload; only worth it if we want a cinematic hero.

## 6. File plan

```
landing/
  app/layout.tsx          # fonts, metadata, drop ThemeProvider
  app/page.tsx            # composes sections
  app/globals.css         # tokens, remove global transition
  components/
    Providers.tsx          # MotionConfig reducedMotion="user"
    sections/ Nav  Hero  RangeScene  ChainShowcase  StrategyScene  ShapShowcase
              RiskShowcase  PipelineScene  Bento  Specs  FinalCta  Footer
    ui/ Section  Reveal  StickyScene  CountUp  Buttons
    charts/ PayoffChart    # shared by hero, strategy morph and bento thumbnail
  lib/blackScholes.ts  lib/payoff.ts  lib/format.ts  lib/links.ts
  data/showcase.ts         # sample market; all option values computed via Black-Scholes
```
Deleted: `Features.tsx`, `HowItWorks.tsx`, `About.tsx`, `Pricing.tsx`, `CTA.tsx`, `Navbar.tsx`, `ThemeToggle.tsx`, `ThemeProvider.tsx` (content migrated into the new sections).

## 7. Phases

1. **Foundation** — tokens, fonts, `motion`, UI primitives, Nav, Footer; remove broken grid/global transitions.
2. **Hero** — `payoff.ts`, `PayoffCurve` with draw-in + drag.
3. **Static sections** — Chain, SHAP, Risk, Bento, Specs, Final CTA (reveal animations only).
4. **Sticky scenes** — Range, Strategy morph, Pipeline.
5. **Assets & polish** — dashboard screenshots, optional 3D surface, OG image, responsive pass (375/768/1280/1920), reduced motion, Lighthouse ≥ 90, `npm run build` + `lint` clean.

## 8. Open decisions (defaults chosen)

- Pricing section: **remove** (a portfolio piece reads better without SaaS tiers).
- Theme toggle: **remove** on landing; dashboard keeps its own.
- 3D hero: **react-three-fiber**, Blender only if we want pre-rendered cinematic frames.

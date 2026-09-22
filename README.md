# Identity

A personal life-OS web app. Home, Stocks, Fantasy, Fitness, and Planner in one
black/white, monochrome, mono-and-grotesk UI.

**Stage 1**: the app shell (5 tabs + sub-tab strip) and the fully-built
**Home** tab — insights feed, spending overview, linked accounts,
transactions, budgets, and savings goals.

**Stage 2**: the fully-built **Stocks** tab — Portfolio, Watchlist, Insights,
and a stock detail page with a real line/candlestick chart toggle and
working range pills.

**Stage 3** (this repo, right now): the fully-built **Fantasy** tab — Lobby,
Matchup, My Team, Ledger, both leagues, league-switching, a snake-draft
board, and a real multi-league debt-simplification settle-up. Fitness and
Planner are still placeholder tabs — the last stage.

## Stack

- [Vite](https://vitejs.dev/) + React + TypeScript
- [Tailwind CSS](https://tailwindcss.com/), themed off the prototype's design
  tokens (see `tailwind.config.ts` and the `:root` variables in
  `src/index.css`)
- [Zustand](https://github.com/pmndrs/zustand) for state, persisted to
  `localStorage`
- [react-router-dom](https://reactrouter.com/) for tab/sub-tab routing
  (`/:tabId/:subSlug`)

## Run it

```bash
npm install
npm run dev
```

Then open **http://localhost:5173**.

Run the unit tests (currently `src/lib/settleUp.ts`, the debt-simplification
engine):

```bash
npm run test
```

## Project layout

```
src/
  components/
    layout/      App shell, top nav, sub-tab nav, tab routing glue
    ui/          Design-system primitives (Card, Pill, Avatar, Dot, ProgressBar, Sparkline, BarChart)
  config/tabs.ts Tab + sub-tab definitions
  data/
    homeSeed.ts    Sample data for the Home tab, mirrors the original prototype 1:1
    stocksSeed.ts  Sample data for the Stocks tab; holding/watchlist fields mirror the
                   prototype 1:1, price history is expanded into a full OHLC series (see below)
    fantasySeed.ts Sample data for the Fantasy tab, mirrors the prototype's two leagues 1:1;
                   draft board is new (see below)
  lib/
    accountability.ts  Generic actual-vs-target alert engine (see below)
    stockInsights.ts   Stocks' rule-based "opinion" engine, built on accountability's evaluateTarget()
    ohlc.ts            Deterministic OHLC series generator + range-based slicing
    settleUp.ts        Generic multi-party debt-simplification engine (see below), with unit tests
    fantasyLedger.ts   Turns a league's standings into settle-up balances for settleUp.ts
    format.ts, dates.ts, clsx.ts
  store/
    useHomeStore.ts    Zustand store for all Home tab data, persisted to localStorage
    useStocksStore.ts  Zustand store for Stocks tab data, persisted to localStorage
    useFantasyStore.ts Zustand store for Fantasy tab data (incl. active league), persisted to localStorage
  tabs/
    home/        Home tab + its six sub-tabs (Insights, Overview, Accounts, Transactions, Budgets, Goals)
    stocks/      Stocks tab + its three sub-tabs (Portfolio, Watchlist, Insights) + stock detail view
    fantasy/     Fantasy tab + its four sub-tabs (Lobby, Matchup, My Team, Ledger) + draft board view
    placeholder/ "Coming soon" placeholder used by Fitness/Planner
  types/domain.ts, stocks.ts, fantasy.ts    Shared data types
```

## The accountability engine

`src/lib/accountability.ts` is deliberately generic: `evaluateTarget()` takes
an `{ actual, target, direction }` reading — `direction: "ceiling"` for things
that shouldn't be exceeded (a budget), `direction: "floor"` for things that
shouldn't fall short (protein intake, task completion rate) — and returns a
`crit` / `warn` / no-flag verdict. `buildAvenueAlerts()` is the one concrete
consumer today: it feeds Home's avenue (budget) data through the engine and
attaches budget-specific copy. Later stages (Fitness, Planner) can reuse
`evaluateTarget()` directly with their own targets and their own copy,
without touching the engine itself.

## The stock insights engine

`src/lib/stockInsights.ts` follows the exact same pattern as the
accountability engine — pure functions that take data and return a verdict,
not tone/note strings sitting in the seed data. It reuses
`evaluateTarget()` directly for the concentration check (a ceiling: position
value as a fraction of held equity vs. a 35% single-position guideline) and
adds two more rules of its own: day-range-as-%-of-price for volatility, and
a sector-coverage check for "does this watchlist stock fill a gap in your
holdings." `buildStockInsights()` runs all three rules per stock and keeps
the highest-severity result, generating the reasoning text from the real
numbers rather than hard-coding it.

## OHLC data and the range pills

The prototype's `history` array was 10 bare numbers with no notion of a
date, and its range pills (1D/1W/.../ALL) didn't actually filter anything —
selecting one just changed which button looked active. `src/lib/ohlc.ts`
generates a full ~1-trading-year, date-indexed OHLC series per stock (seeded
deterministically per ticker, so it's stable across reloads), with the
prototype's original 10 values pinned as the most recent closes. Both the
line chart and the new candlestick chart read from the same sliced series,
and the range pills now genuinely change how much of it is shown.

## The settle-up engine

`src/lib/settleUp.ts` is the third module built on this pattern, and the
most domain-agnostic yet — unlike `accountability.ts` and `stockInsights.ts`,
it has no financial or fantasy vocabulary in it at all. It takes a flat
`{ who, amount }[]` (positive = owed to them, negative = they owe) and
returns the minimal set of payments that zeroes everyone out, using the
standard greedy "largest creditor pays largest debtor" approach — the same
practical algorithm Splitwise itself uses, not a full NP-hard optimal
solver. `src/lib/fantasyLedger.ts` is the one piece that knows what a
fantasy payout means: it turns a league's final standings into a balance
sheet (top-3 payout structure: 60/30/10% of the pot) and hands the combined
balances across every league to `settleUp()`. Because `settleUp()` merges
repeated names before doing anything else, "You" being in both leagues
collapses into one net number rather than two separate settle-ups — see
`src/lib/settleUp.test.ts` for the merge behavior specifically.

## Notable decisions not spelled out in the brief

- **Routing**: sub-tabs get real URLs (`/home/transactions`, etc.) via
  react-router instead of the prototype's in-memory `active`/`activeSub`
  state, so a tab is bookmarkable/shareable and browser back/forward works.
- **Design tokens live as CSS variables**, and Tailwind's theme just points
  at them (`bg-bg`, `text-sub`, `border-neg`, …) rather than hard-coding hex
  anywhere. This keeps a single source of truth and leaves room for a future
  theme swap without touching components.
- **Transaction search/filter is local component state**, not part of the
  persisted store — it's view state, not data, so it resets on tab
  navigation/refresh the way a normal search box would.
- **Subscription next-charge dates** are seeded data (`nextChargeDate` on
  each subscription in `homeSeed.ts`) that didn't exist in the prototype;
  the countdown in `src/lib/dates.ts` is computed from that against the
  current date, and turns amber/red inside a 3-day window.
- **Merchant/subscription avatar colors** are deterministic (hashed from the
  name) rather than random, so a given merchant always gets the same chip
  color across a session and after refresh.
- **Stock detail pages get real URLs** (`/stocks/portfolio/nvda`,
  `/stocks/watchlist/coin`), extending Stage 1's routing decision rather than
  reintroducing the prototype's in-memory `stockDetail` state — so a detail
  page is linkable and back/forward works, and per-ticker chart state
  (range, chart type) resets cleanly when you navigate to a different stock.
- **Concentration/volatility numbers are genuinely computed**, not the
  prototype's hand-written flavor text — e.g. the prototype's NVDA note says
  "31% of your equity book," which doesn't match its own share/price data.
  With real position values NVDA is ~46% of held equity, AAPL ~30%, VTI
  ~24%; I picked a 35% single-position guideline (rather than the
  prototype's fictional 25%) so the concentration rule flags the same single
  holding (NVDA, warn) as the original, but from numbers that actually add
  up.
- **Sector allocation on the Portfolio tab is computed live** from current
  share values instead of the prototype's static, disconnected
  `sectorAlloc` array (which didn't match the holdings either) — same
  reasoning as above.
- **1D range shows the last 5 daily bars**, not a single point — there's no
  real intraday data in this mock dataset, so a literal "1 day" slice would
  render an unreadable single candle.
- **The active league lives in the Fantasy store, not the URL** — unlike
  Stocks' detail pages, switching leagues in the Lobby needs to be
  remembered across Matchup/My Team/Ledger (it is in the prototype too, via
  a shared `activeLeagueIdx`), so it's modeled as persisted selection state
  rather than a route param. The draft board and stock/goal detail pages are
  still URL-based, since those really are "drill into one item" navigation.
- **Each league's "fair share" for settle-up is `potTotal / participant
  count`, not the seeded `buyIn` field** — Office Pool's data has a $20
  buy-in but a $180 pot for 5 people ($100 expected), an inconsistency in
  the prototype's own numbers. `buyIn` is ported and stored, matching the
  brief, but it was never actually rendered anywhere in the prototype
  either; deriving the fair share from the pot keeps the ledger genuinely
  zero-sum, which the settle-up math requires.
- **Draft board is Sunday Guys only** — Office Pool has no roster data in
  the prototype either (it explicitly shows an empty state there), so
  inventing draft picks for it would mean fabricating a roster the rest of
  the app doesn't have. It gets the same empty state instead.
- **Vitest is pinned to 2.1.x**, not the current 3.x line, because 3.x
  requires Vite 6/7/8 and this project is on Vite 5 (matching Stage 1's
  choice). `npm audit` will flag vitest's dev-only tooling chain even at the
  latest 2.1.9 patch; it's a dev-server-only issue (arbitrary file read via
  the Vitest UI/mocker), not something that ships in the built app, and
  fixing it for real means a Vite 6+ upgrade — out of scope for adding tests
  to one module.

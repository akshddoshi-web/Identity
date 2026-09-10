# Identity — Unified Finance + Fitness Platform

A monorepo web + mobile app that unifies personal finance tracking (with a
factor-based investment screener), fitness tracking (calorie/macro logging
down to the ingredient), and a planner that ties lifting, eating, and
spending into one calendar.

> This lives in a subdirectory (`platform/`) of a repo that also contains an
> unrelated sports-betting analytics project at the repo root. Everything
> below assumes your working directory is this `platform/` folder.

**Investment screener disclaimer:** the Investing section of this app is
**educational and informational only — not licensed financial advice**. See
the in-app disclaimer on every recommendation screen.

## Status: what's fully working vs. what needs your own API keys

Everything in the **Build Order** below is implemented and was verified end
to end in development (signup → login → protected pages → every tRPC
procedure → real Postgres) using `scripts/verify-setup.sh`. A few pieces
need real third-party credentials you provide (documented in
[Environment variables](#environment-variables)):

| Feature | Works out of the box? |
|---|---|
| Auth (email/password), all dashboards, planner, training | ✅ Yes |
| Nutrition search + ingredient-level recipe calculator | ✅ Yes (USDA `DEMO_KEY` works, low rate limit) |
| Finance — Plaid Link, transactions, budgets, net worth | ⚠️ Needs a free [Plaid sandbox account](https://dashboard.plaid.com/signup) |
| Investing — Tier 1 factor screener | ⚠️ Needs a free [Alpha Vantage API key](https://www.alphavantage.co/support/#api-key) |
| Investing — Tier 2 risk profile / allocation / backtest | ✅ Yes (built on Tier 1 data once refreshed) |
| Google OAuth | ⚠️ Optional — credentials-based login works without it |
| Background jobs (nightly refresh) | ⚠️ Optional — needs Redis; app works fully without it |
| Mobile app (Expo) | ✅ Boots and bundles; see [Mobile app](#mobile-app-expo) for scope |

**Known limitation:** `next build` (production build) currently fails to
generate the default static `/404` and `/500` fallback HTML export
artifacts, tripping a `<Html> should not be imported outside of
pages/_document` error from Next.js's internal pages-router compatibility
layer. This was extensively bisected (fonts, middleware, `output` mode,
Next patch version, a custom `_document`, the providers tree — none of
these were the cause; it reproduces even in a from-scratch minimal
App-Router project in this environment) and appears to be an environment/
Next 14.2.x interaction rather than anything in this app's code. **It does
not affect `pnpm dev`** — every real route (`/`, `/login`, `/signup`,
`/dashboard`, `/finance`, `/nutrition`, `/training`, `/planner`,
`/investing`, all `/api/*` routes) was verified working over HTTP in dev
mode. If you hit this on `next build` in your own environment, first try
pinning a different Next 14.2.x patch version; if it persists, it doesn't
block local development or `next dev`-based deployment.

## Architecture

```
platform/
  apps/
    web/       Next.js 14 (App Router) — the primary client + API host
    mobile/    Expo (React Native) — shares types/logic with web
  packages/
    shared/    Zod schemas + pure business logic (money, macros, TDEE,
               investment scoring/allocation) — unit tested, framework-free
    api/       Prisma schema/client, tRPC routers, Plaid/USDA/market-data
               integrations, auth helpers, background job definitions
    ui/        Reserved for shared design tokens/components
  docker-compose.yml   Local Postgres + Redis
```

- **Backend:** tRPC routers (`packages/api/src/trpc`) mounted directly as
  Next.js API route handlers (`apps/web/app/api/trpc/[trpc]/route.ts`) —
  no separate API server process needed for local dev, so `pnpm dev` is a
  single process.
- **Database:** PostgreSQL via Prisma (`packages/api/prisma/schema.prisma`).
- **Auth:** Auth.js (NextAuth v4) — email/password (bcrypt) + optional
  Google OAuth, JWT session strategy. Mobile can't use cookies, so it
  exchanges credentials once at `/api/mobile-auth` for a JWT signed with
  the same `NEXTAUTH_SECRET` and sends it as `Authorization: Bearer
  <token>` — one shared session mechanism across both clients.
- **Background jobs:** BullMQ + Redis for nightly market-data refresh and
  Plaid re-sync (`packages/api/src/jobs`). Entirely optional for local
  dev — the app works fully with `REDIS_URL` unset.
- **Money:** every monetary value is stored and computed as integer cents
  (`packages/shared/src/finance/money.ts`) to avoid floating-point drift.

## Prerequisites

- Node.js 20+
- [pnpm](https://pnpm.io) (`corepack enable && corepack prepare pnpm@latest --activate`)
- Docker (for local Postgres + Redis) — or a Postgres instance you already have running

## Quick start

```bash
cd platform
cp .env.example .env            # dummy/dev defaults — works as-is except Plaid/Alpha Vantage
docker compose up -d postgres redis   # or point DATABASE_URL at your own Postgres
pnpm install
pnpm db:migrate                 # applies Prisma migrations
pnpm db:seed                    # demo user: demo@identity.local / password123
pnpm dev                        # starts the web app
```

Open **http://localhost:3000** — sign up or sign in with the seeded demo
account. No further manual steps are needed.

To verify all of this works from a fresh clone in one shot:

```bash
./scripts/verify-setup.sh
```

This checks your Node version, starts Postgres/Redis if Docker is
available, installs dependencies, runs migrations + seed, runs the unit
test suites, boots the dev server, and confirms it responds with HTTP 200
— failing loudly on the first broken step.

## Environment variables

All variables live in `.env` (copy from `.env.example`). Dummy defaults are
enough to boot the app; the table below says what real credentials unlock.

| Variable | Required for boot? | What it unlocks |
|---|---|---|
| `DATABASE_URL` | Yes | Postgres connection (docker-compose default works as-is) |
| `NEXTAUTH_SECRET` | Yes | Session/JWT signing — **change the dummy value for anything beyond local dev** |
| `NEXTAUTH_URL` | Yes | Auth.js callback base URL |
| `ENCRYPTION_KEY` | Yes | AES-256-GCM encryption of Plaid access tokens at rest |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | No | Google OAuth sign-in (credentials login works without it) |
| `PLAID_CLIENT_ID` / `PLAID_SECRET` | No | Bank connections via Plaid Link (sandbox mode = fake institutions, no real bank needed) |
| `PLAID_ENV` | No | `sandbox` (default), `development`, or `production` |
| `PLAID_WEBHOOK_URL` | No | Live transaction-update webhooks in dev (e.g. an ngrok URL) |
| `MARKET_DATA_API_KEY` | No | Tier 1 investment screener (Alpha Vantage free dev-tier key) |
| `USDA_API_KEY` | No | Nutrition food search (works with `DEMO_KEY` out of the box, low rate limit) |
| `REDIS_URL` | No | Background jobs (nightly refresh) — app works fully without it |

### Swapping in production API keys

- **Plaid:** get a free sandbox account at https://dashboard.plaid.com/signup,
  copy the Sandbox `client_id`/`secret` into `.env`. To go live, set
  `PLAID_ENV=production` with production credentials — the code path is
  identical.
- **Market data:** the Tier 1 screener defaults to Alpha Vantage
  (`packages/api/src/investing/marketData.ts`) with a small fixed dev
  universe (`DEV_SCREENER_UNIVERSE`, 10 large-cap tickers) because
  "analyze the entire market" needs a paid, high-volume data feed and would
  blow through the free tier's 5 req/min limit. Swap the two fetch
  functions in that file for Polygon.io/IEX Cloud, and widen the universe
  to the full S&P 500, for production.
- **USDA:** the `DEMO_KEY` works for local dev at a very low rate limit —
  get a free real key at https://fdc.nal.usda.gov/api-key-signup.html.

## Testing

```bash
pnpm test              # all packages
pnpm --filter @identity/shared test   # money/macro/TDEE/scoring/allocation math
pnpm --filter @identity/api test      # encryption, market-data derived factors
```

The shared calculation logic (money math, macro math, budget evaluation,
recurring-charge detection, the investment scoring model, allocation
weighting) has the heaviest test coverage since it's the part most likely
to silently produce wrong numbers — see `packages/shared/src/**/*.test.ts`.

## Mobile app (Expo)

`apps/mobile` is a real, working Expo app (not a stub) that shares
`packages/shared` with the web app — verified by bundling successfully via
Metro (`npx expo export`, 610 modules including `@identity/shared`
resolved through the pnpm workspace) and by typechecking cleanly.

Given this was the lowest-priority item in the build order, its scope is
intentionally narrower than the web app: signup/login (via the shared JWT
mechanism above), a dashboard showing net worth from the same tRPC API, and
a demonstration of `packages/shared`'s BMR/TDEE calculator running natively
with zero network round-trip. It does not (yet) re-implement every web
screen — the finance/nutrition/training/planner/investing screens on
mobile are straightforward extensions of the same `trpcCall()` helper in
`apps/mobile/lib/api.ts`, following the same pattern as the dashboard
screen.

To run it:

```bash
cd apps/mobile
cp .env.example .env    # set EXPO_PUBLIC_API_URL to your machine's LAN IP for a physical device
pnpm start
```

## Build order followed

1. Monorepo scaffold, shared types package, Postgres schema (Prisma) + seed script
2. Auth end-to-end on web (signup/login), then mirrored on mobile via shared JWT
3. Fitness module (nutrition logging, ingredient-level recipe calculator, training)
4. Finance module (Plaid sandbox, transactions, budgets, net worth)
5. Investment Tier 1 factor screener
6. Unified planner (lifting + eating + spending calendar)
7. Investment Tier 2 (risk profile, allocation suggestion, simplified backtest)
8. Mobile app scaffold
9. This README + `scripts/verify-setup.sh`

## Data export

Not yet implemented as a dedicated endpoint. Since every user-owned table
is queryable through the existing tRPC routers (`finance.listTransactions`,
`nutrition.dailySummary`, `training.listSessions`, etc.), a CSV/JSON export
endpoint is a straightforward addition — a `GET /api/export` route that
calls each router's list procedures for the authenticated user and streams
the combined result would follow the exact pattern already used by
`app/api/mobile-auth/route.ts`.

## Deployment notes

- **Web:** Vercel. Set the environment variables above in the Vercel
  project settings; `apps/web` is a standard Next.js App Router project.
- **Database + Redis:** Railway, Render, or Supabase (Postgres) — set
  `DATABASE_URL`/`REDIS_URL` accordingly.
- **Mobile:** Expo EAS Build (`eas build`) once you're ready for
  TestFlight/Play Store distribution; `EXPO_PUBLIC_API_URL` should point at
  your deployed web app's origin.
- **Background jobs:** run `pnpm --filter @identity/api worker` as a
  separate long-running process (e.g. a Railway worker service) once
  `REDIS_URL` is set.

## Security notes

- Plaid access tokens are encrypted at rest with AES-256-GCM
  (`packages/api/src/crypto.ts`) before being stored.
- Passwords are hashed with bcrypt (cost factor 12).
- Login/signup endpoints are rate-limited (5 attempts/minute per email;
  `packages/api/src/auth/rateLimit.ts` — swap for a Redis-backed limiter
  before running multiple app instances).
- No raw financial data is logged.

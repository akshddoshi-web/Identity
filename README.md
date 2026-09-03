# Identity

One system for tracking who you're becoming, expressed through four domains
people already track separately: finance, fantasy sports leagues, nutrition,
and discipline scheduling. The mechanic that ties them together is the
**Identity Thread** — a role you're becoming ("I am a disciplined engineer")
— and the **Identity Score** it rolls up into. See the project brief for the
full concept, including the Correlation Engine, Identity Passport,
Accountability Pods, Seasons, and AI Identity Coach that later phases add.

Two decisions are locked in for this build:

- **Platform**: mobile-first (React Native + Expo), web admin later.
- **Fantasy money model**: virtual currency ("Identity Coin") only for the
  MVP. Real-money rake is Phase 6 and gated on legal review — not started
  without explicit sign-off.

## Structure

```
apps/
  api/      NestJS + Prisma/Postgres backend
  mobile/   Expo (React Native) app, expo-router
packages/
  shared/   Entity types + zod schemas shared by api and mobile
```

## Phase 0 (current)

Auth, user profile, Identity Thread onboarding (2-4 threads), and a
dashboard shell showing the Identity Score UI with zero/mock data. No
pillar (nutrition/finance/schedule/fantasy) logic yet — that's Phases 1-3.

- **Auth**: Clerk. The API's `ClerkAuthGuard` verifies session JWTs; the
  mobile app's `AuthContext` wraps Clerk's hooks. Until a Clerk project is
  configured (`CLERK_SECRET_KEY` / `EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY`),
  both sides fall back to a **dev-mode auth** that trusts a name + email
  the user types in — this keeps the whole app runnable and demoable
  before any external service is wired up.
- **Identity Score**: `IdentityScoreService` on the API computes each
  thread's 0-100 trend score and the weighted composite. Phase 0 has no
  pillar data feeding it, so every thread starts flat at 0 — from Phase 1
  onward this service is extended to pull 30 days of thread-tagged
  activity (meals, transactions, schedule adherence, roster moves).

## Prerequisites

- Node.js 20+, [pnpm](https://pnpm.io) 9+
- PostgreSQL running locally (or update `DATABASE_URL`)

## Setup

```bash
pnpm install
pnpm shared:build

# apps/api
cp apps/api/.env.example apps/api/.env
# edit DATABASE_URL if needed, then:
pnpm --filter @identity/api prisma:migrate

# apps/mobile
cp apps/mobile/.env.example apps/mobile/.env
```

## Running

```bash
# Terminal 1 — API (http://localhost:3000)
pnpm api:dev

# Terminal 2 — mobile (Expo dev server; press w for web, or scan the QR
# code with Expo Go for a device)
pnpm mobile:start
```

With no Clerk keys set, sign in with any name + email on the sign-in
screen — the API's dev fallback trusts it via `X-Dev-User-Email`/
`X-Dev-User-Name` headers, matching what the mobile client sends.

To use real Clerk auth: create a project at
[dashboard.clerk.com](https://dashboard.clerk.com), then set
`CLERK_SECRET_KEY` in `apps/api/.env` and
`EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY` in `apps/mobile/.env`.

## Build phases

Built in order, one phase at a time, each left runnable before the next
starts:

0. **Foundation** (this phase) — auth, thread onboarding, dashboard shell
1. **Nutrition** — food logging (manual/NL-parse/barcode), macro targets,
   first real Identity Score calculation
2. **Schedule/Discipline** — template library, time-block scheduling,
   adherence tracking, calendar sync
3. **Finance** — Plaid Link (sandbox), transaction categorization, budgets,
   net worth, thread tagging
4. **Cross-domain intelligence** — Correlation Engine, AI Identity Coach,
   Identity Passport
5. **Fantasy Leagues** — virtual-currency rosters, scoring, rake, season
   leaderboards (no real money)
6. **Gated — real-money rake** — Stripe Connect, KYC/geolocation, escrow.
   Requires legal review (money transmitter licensing varies by state)
   before any code is written. Not started without explicit sign-off.

# Identity

A personal life-OS web app. Home, Stocks, Fantasy, Fitness, Planner, and a
cross-domain Status view, in one black/white, monochrome, mono-and-grotesk
UI.

**Stage 1**: the app shell (5 tabs + sub-tab strip) and the fully-built
**Home** tab — insights feed, spending overview, linked accounts,
transactions, budgets, and savings goals.

**Stage 2**: the fully-built **Stocks** tab — Portfolio, Watchlist, Insights,
and a stock detail page with a real line/candlestick chart toggle and
working range pills.

**Stage 3**: the fully-built **Fantasy** tab — Lobby, Matchup, My Team,
Ledger, both leagues, league-switching, a snake-draft board, and a real
multi-league debt-simplification settle-up.

**Stage 4**: the fully-built **Fitness** tab — Today, Nutrients, Lifts,
Progress, set-by-set workout logging, a weekly-training-volume-by-muscle-
group chart, and a personal PR/streak history — all wired into the same
accountability engine Home's budgets use.

**Stage 5**: the fully-built **Planner** tab — Week, Goals, a toggleable
Google-Calendar-style time-grid view, Notion-style inline editing, and a
Sunsama-style "plan tomorrow" end-of-day ritual. All five domain tabs are
real; nothing was left as a placeholder.

**Stage 6** (this repo, right now): **Status**, a 6th top-level view that
pulls every domain's already-computed accountability alerts — budget,
stock concentration, calories, workouts, schedule — into one list, ranked
by actual severity across domains that share no units, each item linking
back to its source. This is the payoff Stage 5 closed on: the engine was a
real shared classification function across four tabs, but nothing tied
them together for the person using the app. See "Is Status what makes the
accountability engine a unifying core?" below for how the ranking works and
what it does and doesn't prove.

**Stage 7**: real (sandbox) bank linking via **Plaid**, added to Home's
Accounts sub-tab alongside the seed data, not in place of it. A minimal
serverless backend (`api/`) holds the Plaid secret; the browser never sees
it. See "Plaid (Stage 7): sandbox bank linking" below for the setup, the
architecture, and the explicit "add alongside seed data" decision.

## Stack

- [Vite](https://vitejs.dev/) + React + TypeScript
- [Tailwind CSS](https://tailwindcss.com/), themed off the prototype's design
  tokens (see `tailwind.config.ts` and the `:root` variables in
  `src/index.css`)
- [Zustand](https://github.com/pmndrs/zustand) for state, persisted to
  `localStorage`
- [react-router-dom](https://reactrouter.com/) for tab/sub-tab routing
  (`/:tabId/:subSlug`)
- [Plaid](https://plaid.com/) (sandbox) for real bank-linking on the Accounts
  sub-tab, via Vercel serverless functions under `api/`

## Run it

The frontend runs standalone with seed data only — you don't need a Plaid
account or the API backend just to browse the app:

```bash
npm install
npm run dev
```

Then open **http://localhost:5173**.

### Running Plaid Link too

"Link another account" on Home → Accounts needs the `api/` backend running
alongside Vite, plus a free Plaid account:

1. Sign up at [dashboard.plaid.com](https://dashboard.plaid.com/signup) (no
   payment info needed for sandbox).
2. In the dashboard, go to **Team Settings → Keys** and copy your
   **client_id** and your **sandbox secret** (not production/development).
3. Copy `.env.example` to `.env` and paste those two values in:
   ```
   PLAID_CLIENT_ID=...
   PLAID_SECRET=...
   PLAID_ENV=sandbox
   ```
   `.env` is gitignored — never commit real keys. The frontend never reads
   this file; only `api/` does, and it's never bundled into client code.
4. Run the backend and frontend in two terminals:
   ```bash
   npm run dev:api   # vercel dev, serves api/ on :3000
   npm run dev        # vite, serves the app on :5173 and proxies /api to :3000
   ```
   (`vercel dev` will ask a couple of one-time setup questions the first run —
   accept the defaults, it's just linking the local checkout to a scratch
   Vercel project so it knows how to run `api/`.)
5. Open **http://localhost:5173**, go to Home → Accounts → "Link another
   account," and use Plaid's sandbox test credentials
   (`user_good` / `pass_good`) at any institution in the picker.

Run the unit tests (`src/lib/settleUp.ts`, the debt-simplification engine;
`src/lib/statusOverview.ts`, Status's cross-domain ranking; and
`api/_lib/plaidMapping.ts`, Plaid's account/transaction/category mapping —
Fitness and Planner's own logic is exercised through the app itself rather
than a dedicated test file; see "Did the accountability engine actually
generalize?" below for why nothing there needed new tests):

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
    fitnessSeed.ts Sample data for the Fitness tab; macros/meals/micronutrients/split/bodyweight
                   mirror the prototype 1:1, lift history is expanded into a real set-by-set log
                   (see below)
    plannerSeed.ts Sample data for the Planner tab; blocks/categories/goals mirror the prototype
                   1:1, each block gets a new start/end time for the time-grid view (see below)
  lib/
    accountability.ts  Generic actual-vs-target alert engine (see below)
    stockInsights.ts   Stocks' rule-based "opinion" engine, built on accountability's evaluateTarget()
    ohlc.ts            Deterministic OHLC series generator + range-based slicing
    settleUp.ts        Generic multi-party debt-simplification engine (see below), with unit tests
    fantasyLedger.ts   Turns a league's standings into settle-up balances for settleUp.ts
    liftStats.ts       Derives every lift stat (last session, trend, PR, volume, streaks) from set data
    fitnessInsights.ts Fitness's rule-based alerts, built on accountability's evaluateTarget()
    plannerInsights.ts Planner's rule-based schedule alert, built on accountability's evaluateTarget()
    plannerDates.ts    The shared "today" reference weekday, derived once from the app's reference date
    statusOverview.ts  Pulls every domain's own alert function into one severity-ranked list (see below),
                        with unit tests
    format.ts, dates.ts, clsx.ts
  store/
    useHomeStore.ts    Zustand store for all Home tab data, persisted to localStorage
    useStocksStore.ts  Zustand store for Stocks tab data, persisted to localStorage
    useFantasyStore.ts Zustand store for Fantasy tab data (incl. active league), persisted to localStorage
    useFitnessStore.ts Zustand store for Fitness tab data, persisted to localStorage
    usePlannerStore.ts Zustand store for Planner tab data, persisted to localStorage
    (Status has no store of its own — it only reads the other four)
  tabs/
    home/        Home tab + its six sub-tabs (Insights, Overview, Accounts, Transactions, Budgets, Goals)
    stocks/      Stocks tab + its three sub-tabs (Portfolio, Watchlist, Insights) + stock detail view
    fantasy/     Fantasy tab + its four sub-tabs (Lobby, Matchup, My Team, Ledger) + draft board view
    fitness/     Fitness tab + its four sub-tabs (Today, Nutrients, Lifts, Progress) + lift detail view
    planner/     Planner tab + its two sub-tabs (Week, Goals), the time-grid view, and the
                 plan-tomorrow view
    status/      StatusView — the 6th top-level tab, no sub-tabs
    placeholder/ Kept as the defensive fallback for an unrecognized tabId typed into the URL bar
  types/domain.ts, stocks.ts, fantasy.ts, fitness.ts, planner.ts    Shared data types
  lib/usePlaidConnect.ts  Frontend hook driving Plaid Link (see below)
api/                      Serverless backend (Vercel functions), Plaid-only, holds the Plaid secret
  plaid/create-link-token.ts     POST: starts a Plaid Link session
  plaid/exchange-public-token.ts POST: exchanges Link's public_token for an access_token server-side,
                                  fetches that Item's accounts + transactions, and returns them mapped
  _lib/plaidClient.ts      Builds the Plaid SDK client from env vars; never imported from src/
  _lib/plaidMapping.ts     Pure Plaid → Account/Transaction mapping functions, with unit tests
```

## The accountability engine

`src/lib/accountability.ts` is deliberately generic: `evaluateTarget()` takes
an `{ actual, target, direction }` reading — `direction: "ceiling"` for things
that shouldn't be exceeded (a budget), `direction: "floor"` for things that
shouldn't fall short (protein intake, task completion rate) — and returns a
`crit` / `warn` / no-flag verdict, plus (since Stage 6) a `severity` number
for ranking two flagged things against each other (see "Is Status what makes
the accountability engine a unifying core?" below). `buildAvenueAlerts()` is
the one concrete consumer today: it feeds Home's avenue (budget) data through the engine and
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

## Set-by-set lift logging and the derived stats

The prototype's `lifts` array stored `last`, `trend`, `up`, and `pr` as
separately-authored strings alongside a 10-point `history` sparkline — and,
like the concentration/volatility numbers in Stage 2, they don't actually
agree with their own `history` array (see "the prototype's trend labels
didn't hold up," below). `src/data/fitnessSeed.ts` keeps only the real
primitives (a lift's name, muscle group, training slot, and its set-by-set
`sessions`) and ports the prototype's 10-point history faithfully as the
sequence of weekly top-set weights; everything else — last session, 3-week
trend, all-time PR, the sparkline, weekly training volume, working-set PRs,
and training-split streaks — is computed from that log by
`src/lib/liftStats.ts`. Each lift also carries one session dated well before
the 10-week window, holding the single all-time-max-effort set that backs
the PR line — a real 1-rep-max is a different record category from a
"heaviest top set at your normal working reps," so both are tracked and
neither is hard-coded.

## Fitness: did the accountability engine generalize a second time?

Yes, cleanly, with zero changes to `evaluateTarget()` or its types.
`src/lib/fitnessInsights.ts` is a fourth consumer built on the exact same
shape as `buildAvenueAlerts()` (Stage 1) and the concentration check in
`stockInsights.ts` (Stage 2) — build an `AccountabilityTarget`, call
`evaluateTarget()`, attach copy:

- **Calories vs. goal** — `direction: "ceiling"`, same shape as a budget.
- **Protein vs. goal** — `direction: "floor"`; this is the one the
  prototype's own `buildAlerts()` already special-cased inline (see
  index.html's global accountability function), which is a strong signal
  the engine's ceiling/floor split was already the right generalization —
  Stage 1 just hadn't had a second consumer to prove it yet.
- **Workout completion vs. planned** (2 of 3 Push/Legs/Pull slots this
  week) — `direction: "floor"` again, the same shape as protein, just a
  count instead of a gram measurement. This is the one genuinely new
  proof point: a target that's neither money nor macros still drops into
  `{ actual, target, direction }` without friction.

The only new code is the domain module that builds those three targets and
writes their copy — same division of labor as every consumer before it.
Fitness alerts render on the Today sub-tab, not folded into Home's Overview
card; each tab surfaces its own domain's alerts rather than one cross-tab
rollup, keeping `accountability.ts` itself ignorant of which tab is calling
it.

## Planner: the fifth consumer, and the cleanest fit of all

`src/lib/plannerInsights.ts` wires schedule-completion in as a fifth
consumer, same shape as every one before it — and this is the one case
where I didn't have to design anything. The prototype's own Week view
already computed this exact check inline (`rate = doneCt/all.length`,
crit under 50%, warn under 80%), with a hint that reads *"Same escalation
logic as budget/calorie tracking, applied to your schedule"* — a straight-up
admission in the original code that it belonged in the shared engine and
just never got moved there. `buildScheduleAlert()` is that move: a
`direction: "floor"` target (`actual` = items done, `target` = items
planned) through `evaluateTarget()`, with the prototype's own 0.5/0.8
thresholds passed explicitly (they differ from the engine's floor
defaults, the same way `stockInsights.ts` and `fitnessInsights.ts` both
pass their own thresholds). Zero design decisions needed — the prototype
had already specified the target shape, the thresholds, and the copy; it
just hadn't been asked to route through one shared function yet.

## Stage 5's verdict: the engine as a shared primitive, not yet a unifying experience

This was the honest assessment Stage 5 closed on. It's kept verbatim below
because Stage 6 is a direct answer to it — read it first, then "Is Status
what makes the accountability engine a unifying core?" for what changed.

Both, honestly, and it matters which claim you're making.

**As a shared decision primitive, it's real and it worked.** One function,
`evaluateTarget({ actual, target, direction }, thresholds)`, has made every
crit/warn/none call in this app since Stage 1, across five domains whose
units share nothing — dollars, grams, percent-of-equity, a training-slot
count, a to-do count — and it never needed a signature change, a new
field, or a special case to fit any of them. That's not a small claim: I
designed the ceiling/floor split in Stage 1 speculatively, before Stocks,
Fitness, or Planner existed, and it held on the first try every time after
that. The protein check is the strongest evidence — the *prototype's own
author* had already hand-written that exact floor-check logic inline, and
independently landed on a shape `evaluateTarget()` already covered. The
Planner check is the second — its hint text literally says it belongs in
the shared engine, written before I touched it. Two independent
confirmations from the original design, not just my own after-the-fact
narrative.

**As a unifying product experience, it stops at "shared logic," and that's
a real limit, not a rounding error.** Nothing about what a user sees ties
these five together. Each domain module (`buildAvenueAlerts`,
`stockInsights`, `fitnessInsights`, `plannerInsights`) owns 100% of its own
copy, and that copy — the part a person actually reads — shares no
vocabulary, no visual thread beyond the same alert-card styling, and never
appears in the same place. There is no "everything you're behind on today"
view that pulls from all four; each tab's alerts render only on that tab.
That was a deliberate choice every stage (documented above each time), and
I'd still defend it — a cross-tab rollup wasn't asked for, and bolting one
on now would be scope creep in service of a nicer README sentence, not the
product. But it means the honest description of what got built is "one
well-designed, genuinely reusable risk-classification function, used by
four independent alert generators" — not "an accountability system the
user experiences as one thing." Those are different claims, and only the
first one is true today.

**And Fantasy is the tell.** It has zero consumers, by design, because
points-based competition isn't an actual-vs-target-with-a-goal shape —
there's no "goal" a score is failing to meet, just relative standing. That
the engine correctly has *nothing to say* about an entire domain is a sign
it wasn't stretched to fit everywhere it could reach; it's a sign it was
applied where the shape genuinely existed and left alone where it didn't.
A true "unifying core of the app" would have found a way to touch Fantasy
too, even if forced. This one didn't try, and that restraint is exactly
why it stayed narrow and correct instead of becoming five special cases
wearing one function's clothing.

## Is Status what makes the accountability engine a unifying core?

Mostly yes — Status closes the exact gap Stage 5 named — but building it
surfaced two real things worth being honest about before the verdict.

### What it exposed, before I wrote a line of the view

**`stockInsights.ts` computed a ratio and then threw it away.**
`concentrationFlag()`/`volatilityFlag()` already call `evaluateTarget()` and
get a real `{ tone, ratio }` back, but `StockInsight` (the type every other
part of the Stocks tab consumes) never had anywhere to put it — only
`{ ticker, tone, title, note }`. The other four consumers
(`buildAvenueAlerts`, `fitnessInsights`'s three, `plannerInsights`) all
return `AccountabilityAlert`, which does carry the engine's output. So
Stocks wasn't a logic mismatch, it was a *plumbing* gap: the one consumer
that didn't yet need to rank itself against anything else was the one
consumer that had quietly stopped forwarding a number the engine already
computed. Fixing it meant adding `severity` to `evaluateTarget()`'s return
and threading it through all five consumers' existing code paths (a field
added to an existing return object at each call site, not new logic) — see
the diff in `accountability.ts`, `stockInsights.ts`, `fitnessInsights.ts`,
and `plannerInsights.ts`. This is the "were the per-domain functions
designed with cross-domain comparison in mind" answer: not quite, in one
concrete, fixable place.

**Planner and Fitness independently track "did the workout happen," and
they don't agree.** Planner's Wednesday has a `"Gym — Pull"` to-do block
with its own `done` boolean; Fitness's Wednesday Pull session is tracked
through real set data in `liftStats.ts`. These are two separate models of
the same real-world Wednesday, and nothing reconciles them — a person could
tick the Planner checkbox without ever opening Fitness, or log a full
Deadlift session without ever touching the Planner block, and the app
would show two different, equally confident answers to "did leg day
happen this week" depending which tab you asked. This isn't a bug in
either domain's own logic (each is internally consistent and does exactly
what its tab promises), and Status doesn't paper over it — it can't, since
it only forwards what each domain already believes. I'm not fixing this
now: unifying two independent data models is a real, separate project
(which one is authoritative? does checking one auto-check the other?),
not something a ranking view should quietly decide on the way to shipping.
It's named here so it's a known seam, not a surprise someone finds later.

### The severity rule, explicit

Primary key: **tone** — every `crit` item sorts before every `warn` item,
full stop, regardless of magnitude. This is each domain's own designed
judgment (a domain's crit threshold is always the more extreme line it
chose), so Status defers to it rather than second-guessing it with a
"big warn might matter more than a small crit" override.

Secondary key, within a tone: **severity**, `evaluateTarget()`'s new field
— `ratio - 1` for a ceiling check, `1 - ratio` for a floor check. In plain
terms: *how far past target, as a fraction of target, direction-normalized
so bigger always means worse.* It's what lets a stock 46% over its
concentration guideline, a schedule at 25% completion, and a budget 40%
over rank on one scale without knowing dollars from percent from a task
count — each is reduced to "how far off its own goal, proportionally."

This is a heuristic, not a proof, and it has a real limit worth stating
plainly: because different consumers configure different threshold widths
for `evaluateTarget()` (a budget's warn band is ratio 0.9–1.1, workout
completion's is 0.6–0.85 — call it 4× wider), a `warn` from a
narrow-banded ceiling check and a `warn` from a wide-banded floor check
aren't landing on a perfectly uniform severity scale, even though both
numbers are legitimately "% off target." I chose not to over-engineer a
threshold-relative normalization (it would mean threading each check's
`critRatio`/`warnRatio` into `AccountabilityAlert` too, a bigger touch to
a type every consumer shares, for a correction whose real-world impact I
can't yet demonstrate matters). What I can demonstrate: I hand-verified
this app's actual current alerts against the rule before writing a single
line of `StatusView.tsx`, and `src/lib/statusOverview.test.ts` locks the
result in — including a case that looked like a bug and wasn't: Home's
Food avenue sits at 94.5% of budget (`warn`, "close to its limit"), which
makes its `severity` slightly *negative* (`0.945 - 1`). That's correct,
not broken — within the `ceiling` formula, severity is still monotonic in
ratio across the whole warn band, so Food properly sorts as the *mildest*
warn in the list (see the running app: it's last), even though the raw
number reads oddly in isolation. I don't display the raw severity number
anywhere for exactly this reason — it's an ordering key, not a stat.

### Where it lives, and why

A 6th top-level nav tab, not the root landing route. The alternative — make
`/` show Status before a domain is picked — would've changed what every
existing bookmark/muscle-memory from Stages 1–5 lands on (currently
`/home/insights`), for a feature that's explicitly a *summary of* the five
domains, not a replacement front door to them. A tab is also the
architecturally cheaper fit: `TopNav`/`SubTabNav`/`TabIndexRedirect` are
already built around "a tab is an entry in `TABS`," and Status needed only
one real accommodation to that contract — a tab can have zero sub-tabs
(`subs: []`), handled once, generically, not as a Status-specific hack.
Named "Status," not "Overview," specifically to avoid colliding with
Home's existing Overview sub-tab, and to read as "here's where things
stand" rather than a notifications inbox.

### The verdict

Stage 5 said: real shared classification logic, no unifying product
experience. Status is that missing experience — one ranked list, sourced
from the same four functions, each item routing back to its actual
domain, with a rule I can state in one sentence and defend with a test.
What it does *not* do, and what would be dishonest to claim it does: make
the five domains' *data* agree with each other. Status is only as
trustworthy as its five inputs, and I found one case (Planner vs. Fitness
on "did the workout happen") where those inputs quietly disagree. A
unifying view can rank what each domain believes; it can't make the
domains believe the same thing without becoming a much bigger project
than "Stage 6." That's the honest boundary of what got built here.

## Plaid (Stage 7): sandbox bank linking

### The architecture decision: alongside seed data, not instead of it

Linked (Plaid) accounts and transactions live in the exact same
`useHomeStore` arrays as seed data — `accounts: Account[]`,
`transactions: Transaction[]` — distinguished only by a new optional
`source?: "seed" | "plaid"` field on each. There is no second store, no
"real mode" toggle, no branch anywhere that says "if Plaid is connected,
hide the demo data." Linking an account in the sandbox adds its accounts
and transactions to the lists that already render on Accounts/Transactions;
net worth, the transaction list/search, and everything downstream just sum
and iterate a slightly longer array than before.

This was a deliberate choice, not the only option. The alternative — a
parallel "real" dataset with a mode switch — would better model a
production app (where you'd eventually want to drop the fake data
entirely), but it fails this app's actual constraint: **it has to stay
demoable with fake data for anyone who skips Plaid Link.** A mode switch
means the default view for a first-time visitor is either the seed data
(and linking silently does nothing visible until you flip a switch you
don't know exists) or empty (and the demo is broken until you complete an
OAuth-like flow with a third party just to see the app work). Adding
alongside means the seed data is always there, Plaid Link is a strictly
additive action with an immediately visible result, and the two data
sources need no reconciliation logic — they just co-exist as more rows in
the same arrays, tagged for anyone who wants to filter by source later (the
"· sandbox" label on a linked account's card is the one place that
currently does).

The one piece of merge logic that exists: `addPlaidData()` in
`useHomeStore.ts` de-dupes by id before appending, so re-linking the same
sandbox Item (Plaid issues a new Item, but sandbox test institutions return
the same underlying account_ids) replaces its own rows instead of
duplicating them — it does not touch any other account/transaction, seeded
or previously linked.

### What the backend does, and why it exists at all

The frontend never talks to Plaid directly for anything that needs the
secret. Two endpoints, both server-only (`api/plaid/*.ts`, Vercel
serverless functions):

- **`POST /api/plaid/create-link-token`** — calls Plaid's
  `linkTokenCreate` with this app's `client_id`/`secret` and returns just
  the `link_token` the frontend needs to open Plaid Link. No user input.
- **`POST /api/plaid/exchange-public-token`** — takes the `public_token`
  Plaid Link hands back on success, exchanges it server-side for an
  `access_token` (a real, sensitive, long-lived credential — this is the
  one step that categorically cannot happen in browser code), immediately
  uses that token to fetch the Item's accounts (`accountsGet`) and
  transactions (`transactionsSync`, paginated), maps them to this app's
  types, and returns *only* the mapped accounts/transactions. The
  `access_token` itself is never returned to the client and never
  persisted anywhere — this app has no database. That's a real, named
  scope limit: a linked sandbox account can't be silently re-synced later
  (there's nothing to sync from) — relinking it means going through Plaid
  Link again. Acceptable for a demo of the linking flow; the first thing a
  production version would need is somewhere to store `access_token`
  per-Item, keyed to a real signed-in user this app doesn't have either.

`PLAID_CLIENT_ID`/`PLAID_SECRET` live only in `.env` locally and in
Vercel's project Environment Variables in production — never in any file
this repo commits, and never sent to or read by anything under `src/`.

### Mapping Plaid's shapes onto this app's types

Stage 1's `Account`/`Transaction` types are five stages old and used
everywhere (Status, the accountability engine's budget alerts, Overview's
net-worth math); they weren't widened to match Plaid's shapes. Instead
`api/_lib/plaidMapping.ts` adapts Plaid's richer data down to fit them:

- **Account type** — Plaid's `type`/`subtype` pair maps onto this app's
  closed `"Checking" | "Credit Card" | "Savings" | "Investing"` union
  where there's a confident match (`depository`/`checking` →
  `"Checking"`, `credit` → `"Credit Card"`, etc.); anything with no clean
  bucket (`loan`, sandbox's `"cd"`/money-market subtypes, `"other"`) is
  **skipped**, not forced into the wrong category. `exchange-public-token`
  returns a `skippedAccountCount` for exactly this reason, in case that
  ever needs surfacing in the UI (it doesn't currently render — sandbox's
  default test institutions don't produce any skips in practice — but the
  count exists rather than being silently dropped).
- **Balance sign** — Plaid reports a credit card's balance as a positive
  "amount owed"; this app has always used negative-for-debt (Overview sums
  balances straight into net worth). The mapper flips the sign for
  `"Credit Card"` accounts so a linked card behaves exactly like a seeded
  one in every downstream calculation, with zero special-casing anywhere
  else in the app.
- **Category** — Plaid's `personal_finance_category` taxonomy is far
  richer than this app's six avenue names (Investing, Entertainment,
  Savings, Food, Subscriptions, Income, plus the seed data's implicit
  "Other"). `mapPlaidCategory()` is a best-effort heuristic, not a real
  categorizer: a short table of high-confidence Plaid categories maps onto
  the closest existing avenue vocabulary; everything else becomes
  `"Other"` rather than guessing. This affects display/filtering in the
  Transactions list only — **it does not feed avenue `spent` totals**,
  which stay purely seed-data-driven; teaching a linked transaction to
  count against a budget's spend would mean designing how a Plaid category
  maps onto avenue budgets with actual confidence, not shoehorning it in
  as a side effect of a demo-scope linking feature.
- **Amount sign** — same flip as balance, for the same reason
  (Plaid: positive = money out; this app: negative = money out).

### Running it locally

Two processes, because Vite serves the static frontend and `api/` needs
Vercel's serverless runtime (`vercel dev`) to execute — see "Run it" above
for the exact commands. `vite.config.ts` proxies `/api/*` from :5173 to
:3000 in dev so the frontend's `fetch("/api/plaid/...")` calls work
identically to how they'll resolve in production, where Vercel routes
`/api/*` to these same function files with no proxy needed at all (same
project, same deploy — no second host to configure or pay for).

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
- **A lift detail page gets a real URL** (`/fitness/lifts/bench-press`),
  same reasoning as stock and league-draft detail pages: it's "one specific
  thing I'm looking at right now." "Which day" and "which meal" never
  needed a routing decision at all — Today is fixed to the current day (the
  prototype has no historical diary to browse) and meals render inline with
  no drill-down page, so neither one is "one specific thing" navigation in
  what was actually built.
- **The prototype's trend labels didn't hold up under real computation** —
  a third instance of the pattern from Stages 2 (concentration %) and 3
  (buy-in vs. pot). Comparing each lift's ported history 3 entries back
  (its "3wk" framing, at one session/week) gives a uniform +5 lb for all
  four lifts, including Deadlift — whose prototype label claims "flat."
  Deadlift's real 10-week window genuinely does plateau (one working-set PR
  in the whole window, at week 2 — see Progress's personal history), it's
  just that the specific 3-week comparison window isn't where that
  plateau shows up numerically. I kept the honest computed number rather
  than re-engineering the data to force "flat" back out of it.
- **"Planned training days" means 3 (Push/Legs/Pull), not the 5 non-rest
  calendar days in `split`** — the split template calls for Push and Pull
  twice each per week, but the lift log (like a real lifter's actual habits)
  only reliably has one dated session per muscle group per week. Grading
  against 5 when only 3 session-types exist in the data would make the
  workout-completion check permanently and uninformatively "crit." 3 is
  what the underlying set data can actually attest to.
- **Workout "completion" is measured by session depth (2+ sets logged),
  not by whether a session happened at all** — this keeps a lift's full
  10-week weight-progression history intact (every week has a real
  top-set weight, so the sparkline and PR detection never have gaps) while
  still giving the accountability engine and the streak timeline a genuine,
  set-data-derived signal: a single rushed set on deadlift day reads as an
  incomplete Pull slot, exactly like the app's live demo state has it for
  the current week.
- **Only "plan tomorrow" gets a URL** (`/planner/week/plan-tomorrow`) — it's
  the one piece of Planner that's "one specific thing being looked at right
  now," same reasoning as a stock/lift detail page or the Fantasy draft
  board. The list/grid view toggle is local component state, not store or
  URL — same call as Stocks' line/candle toggle, since it's a rendering
  mode for whatever's already on screen, not a drill-down or a
  cross-sub-tab context. Planner has no equivalent of Fantasy's
  `activeLeagueId`: Week and Goals don't share a selectable "which one am I
  looking at," so nothing beyond the data itself lives in
  `usePlannerStore`.
- **Blocks gained `start`/`end` time fields that don't exist in the
  prototype** — the time-grid view has no way to lay blocks out in a day
  without some notion of when they happen. Each block got a specific,
  reasonable time authored by hand (not derived from nothing), the same
  way Stage 1 added `nextChargeDate` to subscriptions for the countdown
  feature. The list view and the time-grid view render the same
  `PlannerBlock` records — including inline editing, which lives in one
  shared `PlannerBlockRow` component used by both — so "two renderings,
  one dataset" is literally true of the code, not just the data.
- **"Today" for Planner is derived, not hand-picked** — `plannerDates.ts`
  computes the weekday from the same reference date (`2026-09-22`, a
  Tuesday) the other three dated seeds already anchor to, rather than
  hardcoding `"Tue"` as a magic string disconnected from the rest of the
  app. It happens to land on a day with exactly one unfinished item, which
  makes "plan tomorrow" demo something real instead of an empty state.
- **Dropping a block in "plan tomorrow" really deletes it** — no dropped-
  items archive. The brief's concern was items vanishing *silently*
  (auto-rollover, or just falling off the list unnoticed); a person
  explicitly clicking "Drop" after being shown the item is the opposite of
  that, so an audit trail wasn't necessary to satisfy the actual
  requirement, and I didn't add one un-asked.
- **A Status item's link target is the most specific/actionable page for
  it, not necessarily the literal tab it also renders on** — matching the
  brief's own stock-detail-page example rather than a stricter "link to
  where this exact text is shown" reading. Home's budget alerts render on
  Overview but link to Budgets (the full per-avenue breakdown); Fitness's
  calorie/protein alerts link to Today (where they render) but
  workout-completion links to Lifts (where you'd actually go log a missed
  session) instead. Each mapping is a couple of lines in
  `statusOverview.ts`, not a new pattern — just picking the better
  destination per alert id.
- **Status's empty state is verified by unit test, not a screenshot** — the
  app has no interactive controls anywhere that zero out spending,
  concentration, volatility, or schedule completion all at once (Planner's
  checkboxes are the only real "fix an alert" interaction that exists), so
  there was no way to reach the empty state through the live UI to
  screenshot it. `src/lib/statusOverview.test.ts` constructs the on-track
  inputs directly and asserts `buildStatusItems()` returns `[]`; the JSX
  branch that renders on an empty array is a two-line ternary, low enough
  risk that I didn't chase a live repro for it.

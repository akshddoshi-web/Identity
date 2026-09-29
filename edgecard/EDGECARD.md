# Edge Card

A daily NBA + NFL betting **decision engine**. It does not try to pick winners.
It looks for bets where our calibrated probability beats the sportsbook's
no-vig probability by more than the vig — and says **NO BET** when nothing
does. Paper mode is on by default. Nothing here is a guarantee.

Everything runs on free infrastructure: free public data, GitHub Actions
(free for public repos), results stored in this repo's `edgecard-data`
branch, and a Streamlit Community Cloud page. **No paid APIs, no API keys,
no credits.**

---

## What the card shows

For each league, three tiers — **SAFE** (win prob ≥ 55%, 1–2 legs, edge ≥ 2%),
**MODERATE** (20–45%, 1–4 legs), **LONG SHOT** (3–15%, must still be +EV or
it says `NO LONG SHOT TODAY`). For every pick:

- bet, best book and price, and the **worst price you should still take**
- model probability vs no-vig market probability vs the price's break-even
- edge %, EV per $100, suggested stake (¼ Kelly, capped at 2% of bankroll
  per bet and 5% per day)
- top 3 reasons, with numbers
- every news / injury flag checked, with source and timestamp
- `WAIT — recheck after <time>` if a key player is unresolved or the line
  moved sharply against us

## How probabilities are made (and why most days will be NO BET)

1. **Fair value** comes from the market: each book's two-way no-vig
   probability is turned into an implied margin/total distribution
   (key-number aware — extra mass on 3 and 7 in the NFL), and the median
   across books is the fair distribution. That prices any line, including
   alternates.
2. **Our model** (gradient-boosted mean + fitted variance, walk-forward
   trained) can move that fair value only by a weight `w` it has **earned out
   of sample**: `logit(p) = logit(market) + w · (logit(model) − logit(market))`.
   `w` is fitted on earlier seasons' out-of-sample predictions and forced to
   0 unless a likelihood-ratio test (α = 0.01) says the model's disagreement
   with the closing line is real.
3. **Edges** are then (a) prices at one book that beat the multi-book fair
   value by more than the vig (line shopping), and (b) model edges only where
   `w > 0`.
4. **Parlays** use one book, and joint probabilities come from a correlated
   Monte Carlo simulation (10,000 draws; QB yards ↔ receiver yards ↔ game
   total ↔ game script), never from multiplying same-game legs.

### Current backtest verdict (NFL, walk-forward 2020–2026)

The honest result, reproduced every week by `edgecard backtest`:

- The model does **not** beat the no-vig closing line in log loss for
  moneyline, spread, or total. The model alone is worse than the market
  (≈ +0.03 log loss on moneylines, ≈ +0.01 on spreads/totals).
- So `w = 0` in every NFL market: **NFL picks come only from line
  shopping**, never from the model's opinion.
- Situational hypotheses (each tested alone vs the base model, kept only if
  they lower out-of-sample log loss in at least half the seasons):
  kept — pressure/red-zone, turnover luck, cohesion (QB change, trades,
  new high-usage arrivals), weather, head-to-head, altitude;
  dropped — opponent adjustment, special teams, fatigue/travel, motivation.
  "Kept" means it helps the model, not that the model beats the market.
- Player props: the simulated distributions are roughly calibrated against
  real 2024 outcomes (means within ~1–7%) and beat a naive baseline on some
  markets, not all. No free source has prop **prices**, so props are shown
  in **shadow mode** (tracked, never recommended) until live tracking proves
  them.

The NBA backtest (`edgecard backtest --league nba`) publishes its own
verdict to `reports/backtest_nba.json` and the site's Backtest tab.

## Data sources (all free, all verified from GitHub's servers)

| Need | Source | Notes |
|---|---|---|
| NFL history, closing lines, pbp/EPA, snaps, injuries, depth charts, NGS, trades | nflverse (GitHub releases + nfldata) | real closing prices with vig back to 2006 |
| Odds, many books | ESPN core API (DraftKings, Caesars, Betfair, … open/current/close) | no key; ESPN blocks browser User-Agents from cloud IPs, so none is sent |
| Odds, more books + opening line | Action Network public scoreboard | no key |
| Exchange prices | Kalshi public API | converted after Kalshi's taker fee |
| Player prop **lines** | ESPN (DraftKings) | lines only — prices are not published anywhere free |
| Injuries / practice status | ESPN injury feed, nflverse weekly reports | official designations |
| News (last 48h) | Google News RSS per player/team, ESPN news, PFT, CBS | keyword rules → structured flags |
| Weather | Open-Meteo forecast at kickoff hour | outdoor NFL venues only |
| NBA history | ESPN scoreboards (scores + lines) and pbpstats.com (possessions) | see below |

**nba_api is blocked from GitHub's servers.** `stats.nba.com` times out and
`cdn.nba.com` returns 403 from GitHub runners (tested). Edge Card uses ESPN
+ pbpstats instead. What that costs: no player-tracking data and no
lineup on/off splits at scale, so the NBA "cohesion" and "ego/role
conflict" hypotheses are not tested yet. If you want them: run NBA
ingestion on your own computer as a GitHub **self-hosted runner** (free),
where `nba_api` works.

## Commands

```bash
cd edgecard
pip install -r requirements.txt && pip install -e .
export EDGECARD_DATA_DIR=./data/store     # or a checkout of the edgecard-data branch

edgecard ingest   --league nfl|nba|both   # history (incremental for NBA)
edgecard backtest --league nfl|nba        # walk-forward + ablation + production model
edgecard snapshot --league both           # odds + prop lines from every free book
edgecard today    --league nfl|nba|both   # build + publish the card
edgecard settle   --league both           # closing lines, results, CLV
edgecard report                           # weekly CLV / ROI / calibration
python -m pytest -q                       # includes leakage + vig-math tests
```

## Schedule (GitHub Actions, `.github/workflows/edgecard-pipeline.yml`)

- ~10:00 ET daily — settle yesterday, snapshot odds, build the card
- ~17:00 ET daily — recheck news/injuries/lines, update the card
- evenings — pre-game line captures (closing lines for CLV)
- Tuesdays ~06:00 ET — re-ingest history, re-run both backtests

GitHub's scheduler can run 5–30 minutes late; closing lines are the last
capture before kickoff.

## Tracking & honesty

- Every recommendation is appended to `ledger/recommendations.csv` before
  the game and never edited.
- `settle` records the closing line, CLV **at our line**, result and paper
  profit; the weekly report breaks CLV, ROI and calibration down by tier
  and bet type.
- Once 200+ bets are settled, negative average CLV shows a red warning on
  the site and the card.
- Paper mode is on (`config/config.yaml → edgecard.paper_mode`). Leave it on
  until live CLV is positive over 200+ bets.

## Privacy note

This repo is public, so the `edgecard-data` branch (cards, ledger) is
public too. The site password protects the page, not the underlying files.
If that matters, make the repo private — Actions still has 2,000 free
minutes/month (this uses roughly 600–800), but the Streamlit app would then
need a read-only GitHub token in its secrets to read the data branch.

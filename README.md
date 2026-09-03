# Sports Betting Analytics & Decision-Support System

A rigorous edge-detection and bankroll-management framework for **NFL, NCAAF, and NBA**,
modeled on how professional/sharp bettors actually operate.

## What this is NOT

This is **not** a "guaranteed winner" system, a black box that spits out picks, or a
promise of profit. Sports betting markets are efficient enough that durable edges are
small (a few percent), noisy, and easy to talk yourself into seeing when they aren't
there. Every output in this system is designed to make it hard to fool yourself:

- Model probabilities are always shown next to de-vigged market probabilities, not in
  isolation.
- No performance claim is presented without a sample size and a confidence interval.
- Samples under **200 bets** are explicitly flagged as statistically meaningless — the
  system will tell you this even when the record "looks good."
- Every prediction is logged, timestamped, and immutable *before* the game happens.
  There is no code path that lets you retroactively edit a logged prediction to cherry-pick
  wins.
- A Monte Carlo simulator shows you that even a genuine, durable 55% edge produces long
  losing streaks — so a single backtest equity curve is never presented as "the" outcome.

If you use this system for real-money decisions, understand that: (1) past model
performance does not guarantee future performance, (2) sportsbooks limit or ban
consistently winning accounts, (3) you can and will lose money even when the model is
"right" in expectation, and (4) nothing here is financial advice.

## Architecture

```
config/                 YAML configuration (thresholds, Kelly fraction, bankroll caps)
data_pipeline/           Ingestion: games, advanced stats, odds (opening/closing), DB layer
models/                  Elo baseline, feature engineering, GBM models, walk-forward backtesting
edge/                    De-vigging, edge detection, CLV tracking
bankroll/                Fractional Kelly sizing, bankroll tracking, Monte Carlo simulation
guardrails/              Immutable prediction logging, disclaimers, sample-size gating
dashboard/               Streamlit dashboard
scripts/                 Synthetic sample-data generator + end-to-end demo runner
tests/                   Unit tests for the math-critical modules (de-vig, Kelly, Elo, CLV)
```

## Data sources (you must supply credentials)

This repo ships **no** live data and **no** API keys. It defines the ingestion interfaces
and a SQLite storage schema; you point it at real sources:

| Data | Suggested source | Needs API key? |
|---|---|---|
| Schedules / scores / injuries | [SportsDataIO](https://sportsdata.io), [nflfastR](https://www.nflfastr.com/) data releases (NFL), [cfbfastR](https://cfbfastr.sportsdataverse.org/) (NCAAF), [nba_api](https://github.com/swar/nba_api) | Yes for SportsDataIO; nflfastR/cfbfastR/nba_api are free but rate-limited |
| Advanced stats (EPA, DVOA-style, ratings) | nflfastR / cfbfastR play-by-play (compute EPA yourself), NBA Advanced Stats (stats.nba.com via nba_api) | No (compute-it-yourself), or SportsDataIO for pre-computed |
| Odds — current & historical, opening & closing | [The Odds API](https://the-odds-api.com/), [SportsDataIO Odds](https://sportsdata.io/odds-data-api) | **Yes** — set `ODDS_API_KEY` env var |
| Weather | [OpenWeatherMap](https://openweathermap.org/api) or [Visual Crossing](https://www.visualcrossing.com/) historical weather API | Yes |

Because CLV tracking requires historical **closing** lines (not just current odds), and
most free odds APIs only expose a rolling window of current lines, a real deployment needs
either (a) a paid historical-odds provider, or (b) your own scheduled scraper that snapshots
lines pre-game and stores closing lines itself going forward. The pipeline is built to do
(b) out of the box (`data_pipeline/ingest_odds.py` + a cron/scheduler), and to backfill from
(a) if you have it.

## Quickstart (synthetic data — no API keys required)

```bash
pip install -r requirements.txt
export PYTHONPATH=.                             # needed so the top-level packages import cleanly
python scripts/generate_sample_data.py          # builds data/betting.db with synthetic history
python scripts/run_pipeline_demo.py             # trains Elo + GBM, backtests, computes edges/CLV
streamlit run dashboard/app.py                  # view the dashboard (also inserts repo root on sys.path itself)
```

Run the test suite with `pytest` from the repo root (a `conftest.py` + `pytest.ini` handle the import path automatically, no `PYTHONPATH` needed there).

The synthetic generator exists **only** to exercise the pipeline end-to-end (schema
validity, backtest mechanics, Kelly sizing, dashboard rendering) so you can see the system
work before wiring in real data. Any "edges" or "performance" you see against synthetic
data are meaningless by construction — the synthetic outcomes are generated independently
of the synthetic "market" line with injected noise, not from real markets.

## Live odds ingestion

`data_pipeline/ingest_odds.py` implements a client for **The Odds API** as the reference
integration (spreads, totals, moneylines, multiple books). Set:

```bash
export ODDS_API_KEY=your_key_here
```

Swap in SportsDataIO or another provider by implementing the same `OddsClient` interface.

## Kelly sizing & risk

Bet sizing uses **fractional Kelly** (configurable, default quarter-Kelly) derived from the
model's de-vigged edge and the offered price, hard-capped at a configurable percentage of
bankroll (default 2%) regardless of what Kelly says. See `config/config.yaml`.

## Disclaimers module

`guardrails/disclaimers.py` is imported by the dashboard and by every report-generating
function; it is not decorative. It surfaces variance context (Monte Carlo bankroll paths)
alongside every ROI or CLV claim.

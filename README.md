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
scripts/                 Synthetic sample-data generator, end-to-end demo runner, daily live report
tests/                   Unit tests for the math-critical modules (de-vig, Kelly, Elo, CLV, live features)
```

## Data source availability — honest status

This section says, plainly, what is real and validated, what is real but unvalidated, and
what is still synthetic, as of the last time this repo's own data was refreshed. Don't take
any dashboard number on faith without checking this first.

| Sport | Source | Status |
|---|---|---|
| **NFL** | [nflverse-data](https://github.com/nflverse/nflverse-data) play-by-play (public GitHub release assets, no key) | ✅ Real. Ingested and walk-forward backtested — see numbers below. |
| **NCAAF** | [sportsdataverse/cfbfastr-data](https://github.com/sportsdataverse/cfbfastr-data) (schedules + play-by-play + embedded closing lines, public repo, no key) | ✅ Real. Ingested and walk-forward backtested — see numbers below. FBS-vs-FBS games only. |
| **NBA** | [nba_api](https://github.com/swar/nba_api) (stats.nba.com) | ⚠️ Code written (`data_pipeline/sources/nba_nba_api.py`), **not executed or validated**. See that module's docstring for why and what to do about it. |
| **Live odds (all sports)** | [The Odds API](https://the-odds-api.com/) | ⚠️ Client code written and wired to `ODDS_API_KEY` (see below), **not exercised against the live endpoint** in this repo's own development. Validate it yourself once you have a key and normal internet access. |

Both real sports also came with **real historical closing lines** — nflverse and
cfbfastR-data each embed the closing spread and total for every game — so the walk-forward
Brier/log-loss/CLV-style comparisons below are against real market numbers, not fabricated
ones. Neither source has historical moneyline, so moneyline market data is live-only (via
The Odds API) for both sports right now. See `data_pipeline/sources/nfl_nflverse.py` and
`data_pipeline/sources/ncaaf_cfbfastr.py`'s docstrings for the exact fields used, the sign
conventions (verified against real blowout games, not assumed), and known gaps (no real
travel distance for NCAAF, no weather for NCAAF, no referee data for either).

### Real ingestion

```bash
# NFL: no setup needed, pulls directly from nflverse-data's GitHub releases
python scripts/ingest_real_data.py --sport NFL

# NCAAF: clone the data repo once (public, no key; ~7GB, shallow clone keeps it manageable)
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/sportsdataverse/cfbfastr-data /home/user/sportsdataverse/cfbfastr-data
python scripts/ingest_real_data.py --sport NCAAF

# both at once, with the default ~9-10 season windows:
python scripts/ingest_real_data.py --sport ALL
```

**Do not `pip install nfl_data_py` or `nba_api` into this project's main environment.**
`nfl_data_py` pins `pandas<2.0` and `nba_api` pins `numpy<2.0` — either one, installed
alongside this repo's `pandas>=2.1`/`numpy>=1.26`, gets silently downgraded by pip's
resolver and **corrupts the rolling-feature engineering in `models/features.py`** (this
happened during development: `pip install nfl_data_py` downgraded pandas to 1.5.3 and broke
a walk-forward feature-alignment test with no error, only a silently wrong value). This
repo's own NFL/NCAAF ingestion never imports either package — it talks to the raw data
files directly. If you need `nba_api`, install it in its own virtualenv (see
`data_pipeline/sources/nba_nba_api.py`).

### Odds API key setup

1. Get a key from [the-odds-api.com](https://the-odds-api.com/) (free tier available).
2. Copy `.env.example` to `.env` in the repo root and paste your key in:
   ```bash
   cp .env.example .env
   # then edit .env: ODDS_API_KEY=sk-your-real-key-here
   ```
   `.env` is already in `.gitignore` — it will never be committed. `data_pipeline/config.py`
   loads it automatically (via `python-dotenv`) on every run; you don't need to `export` it
   yourself unless you'd rather set it as a real shell/CI environment variable instead.
3. On Streamlit Community Cloud, don't use `.env` at all — see the **Deploying to Streamlit
   Community Cloud** section below for the Secrets-store equivalent, which
   `data_pipeline/config.py::odds_api_key()` also checks automatically.

Because this repo's own development sandbox blocked outbound traffic to everything except
GitHub and PyPI, **`api.the-odds-api.com` was never actually reached from that session** —
the client code (`data_pipeline/ingest_odds.py`) is written against the real, documented
API, but run `python scripts/daily_report.py` yourself once you have a key and confirm it
pulls real games before trusting its output.

## Quickstart (synthetic data — for testing pipeline mechanics only)

```bash
pip install -r requirements.txt
export PYTHONPATH=.                             # needed so the top-level packages import cleanly
python scripts/generate_sample_data.py          # builds data/betting.db with FAKE data
python scripts/run_pipeline_demo.py             # trains Elo + GBM, backtests, computes edges/CLV
streamlit run dashboard/app.py                  # view the dashboard (also inserts repo root on sys.path itself)
```

Run the test suite with `pytest` from the repo root (a `conftest.py` + `pytest.ini` handle the import path automatically, no `PYTHONPATH` needed there).

The synthetic generator exists **only** to exercise the pipeline end-to-end (schema
validity, backtest mechanics, Kelly sizing, dashboard rendering) so you can see the system
work before wiring in real data. Any "edges" or "performance" you see against synthetic
data are meaningless by construction. **Prefer `scripts/ingest_real_data.py` (above) for
anything you intend to actually look at.**

## Live odds ingestion

`data_pipeline/ingest_odds.py` implements a client for **The Odds API** as the reference
integration (spreads, totals, moneylines, multiple books). Set:

```bash
export ODDS_API_KEY=your_key_here
```

Swap in SportsDataIO or another provider by implementing the same `OddsClient` interface.

## Daily live edge report

```bash
export ODDS_API_KEY=your_key_here
python scripts/daily_report.py                 # console report
python scripts/daily_report.py --csv today.csv  # also write a CSV
python scripts/daily_report.py --edge-threshold 0.04 --bankroll 25000  # overrides
```

For each of NFL/NCAAF/NBA, this pulls today's scheduled games and pre-game odds, trains
that sport's production models on all history currently in the database (refusing to do so,
per sport, if there isn't enough validated history — see `models/production.py`), projects
each team's real trailing form onto today's matchup with zero leakage
(`models.features.build_live_feature_rows`), de-vigs the market price on moneyline/spread/
total and compares to the model, flags games clearing the configured edge threshold, sizes a
suggested stake with capped fractional Kelly against your current bankroll, and — before
printing anything — logs each flagged prediction through `guardrails/prediction_log.py` so
it's timestamped and cannot later be edited or cherry-picked. If nothing clears the bar that
day, it says so explicitly rather than lowering the threshold to manufacture a pick.

Team names returned by your odds provider must match the team names in your historical
`games`/`team_game_stats` data for the rolling-form lookup to find them — reconcile any
naming differences between your schedule/stats source and your odds source before relying
on this in production.

## Validated backtest results (real data)

Walk-forward results from `models/production.py` against the real NFL/NCAAF data described
above (config's `sports.<SPORT>.rolling_window_games` as the minimum training window, retrain
every `max(50, window/10)` games — see that file). A coin-flip model scores Brier=0.25,
LogLoss=0.693; lower is better on both.

| Sport | OOS games (n) | GBM Brier | GBM LogLoss | Elo Brier | Elo LogLoss |
|---|---|---|---|---|---|
| NFL (2015-2023, 9 seasons) | 1,099 | 0.2404 | 0.7976 | **0.2319** | **0.6623** |
| NCAAF (2012-2021, 10 seasons, FBS only) | 5,251 | 0.1926 | 0.5877 | **0.1871** | **0.5516** |

**Honest read: the plain Elo baseline currently beats the gradient-boosted model on both
real sports, out of sample.** By this project's own stated design principle (see
`models/elo.py`'s docstring: Elo exists as "the sanity-check benchmark... if the GBM can't
beat a simple Elo rating out-of-sample, the extra complexity isn't earning its keep"), the
honest conclusion is that the GBM's current feature set/hyperparameters are NOT yet earning
their complexity on real data. Plausible reasons, untested: 300 trees is likely too many for
fold sizes in the low thousands (overfitting on ~34 rolling-average features derived from
noisy 8-game windows); no injury data; no PFF grades; no referee assignments. Regularizing
the GBM harder (fewer trees, shallower depth, stronger L2) and/or blending it with Elo rather
than replacing it are the natural next steps — neither has been tried yet. NCAAF's larger
talent gaps between teams make it more predictable than NFL for both models, which matches
common football intuition and is not itself surprising.

**None of the above is an edge claim.** Beating a coin flip on win-probability calibration is
a necessary condition for having a tradeable signal, not a sufficient one — the number that
actually matters is model probability vs. the DE-VIGGED MARKET's probability (the `edge/`
module), and that can only be assessed with real, dated CLV tracking over a real bet sample,
which requires actually running `scripts/daily_report.py` against live odds for a while (see
`edge_detection.min_sample_size_for_significance` = 200 bets before ANY edge/CLV number here
should be treated as meaningful). This system has zero real logged bets as of this writing.

## Kelly sizing & risk

Bet sizing uses **fractional Kelly** (configurable, default quarter-Kelly) derived from the
model's de-vigged edge and the offered price, hard-capped at a configurable percentage of
bankroll (default 2%) regardless of what Kelly says. See `config/config.yaml`.

## Disclaimers module

`guardrails/disclaimers.py` is imported by the dashboard and by every report-generating
function; it is not decorative. It surfaces variance context (Monte Carlo bankroll paths)
alongside every ROI or CLV claim.

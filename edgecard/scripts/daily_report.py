"""Daily pre-game edge report across NFL, NCAAF, and NBA.

Run as: python scripts/daily_report.py [--csv PATH] [--edge-threshold PCT] [--bankroll AMOUNT]

For each sport currently in season (determined simply by whether the odds
API has any games scheduled today — an out-of-season sport naturally
returns none), this:

  1. Pulls today's games + pre-game odds from data_pipeline.ingest_odds's
     OddsAPIClient (needs ODDS_API_KEY — see README).
  2. Trains this sport's production models (models/production.py) on all
     available history in the database, including an out-of-sample
     walk-forward pass used ONLY to get honest calibration and residual-std
     numbers — never to pick the final model.
  3. Projects each of today's teams' trailing form onto today's matchup
     without leaking any information about today's game itself
     (models.features.build_live_feature_rows).
  4. De-vigs the market price on each of moneyline / spread / total and
     compares to the model's probability for that side (edge/ module).
  5. Flags games where |edge| clears the configured threshold, sizes a
     suggested stake with fractional Kelly (bankroll/kelly.py) capped at the
     configured max % of bankroll, and logs the prediction through
     guardrails.prediction_log BEFORE printing it — so nothing shown here
     can later be edited or cherry-picked.
  6. Prints a console report (and optionally writes a CSV). If nothing
     clears the bar, the report says so plainly — it does not lower the
     threshold to manufacture picks.

A sport is skipped (with an explicit, printed reason) rather than forced
through when: there's no game today, there isn't enough validated history to
trust a production model yet (models.production.InsufficientHistoryError),
or a market's odds simply aren't available for a given game.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from dataclasses import asdict

import pandas as pd
import requests

from data_pipeline.config import load_config
from data_pipeline.db import connect
from data_pipeline.ingest_games import upsert_games
from data_pipeline.ingest_odds import OddsAPIClient, parse_odds_api_event, game_id_from_odds_event
from data_pipeline.queries import load_games, load_team_game_stats, bet_ledger_all
from data_pipeline.schema import GameRecord, OddsSnapshot
from edge.edge_detection import compute_edge
from bankroll.kelly import size_bet
from bankroll.bankroll_tracker import compute_bankroll_stats, bankroll_headline
import sqlite3

from guardrails.prediction_log import log_prediction, make_prediction_id, PreGameLockViolation
from guardrails.disclaimers import full_disclaimer_block, small_sample_warning
from models.features import build_live_feature_rows
from models.gbm_model import margin_to_win_prob
from models.production import train_production_models, InsufficientHistoryError

SPORTS = ("NFL", "NCAAF", "NBA")
MODEL_NAME = "xgb_gbm"
MODEL_VERSION = "production_v1"


# --------------------------------------------------------------------------- #
# Today's slate
# --------------------------------------------------------------------------- #


def fetch_todays_events(client: OddsAPIClient, sport: str) -> list[dict]:
    """Games with a commence_time between now and the end of today (UTC).
    A sport out of season simply has no events in this window — that's how
    "whichever are in season" is satisfied without any separate schedule
    check. This UTC-calendar-day window is a simplification: a West Coast
    night game can spill past midnight UTC into "tomorrow" and get excluded.
    A production deployment should group by each league's own slate/local
    date instead; this is good enough for a daily batch report.
    """
    events = client.fetch_current_odds(sport)
    now = dt.datetime.utcnow()
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
    todays = []
    for event in events:
        try:
            commence = dt.datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00")).replace(tzinfo=None)
        except (KeyError, ValueError):
            continue
        if now <= commence <= end_of_day:
            todays.append(event)
    return todays


def _last_game_dates(games_sorted: pd.DataFrame) -> dict[str, str]:
    """games_sorted must be ascending by game_date; last write per team wins."""
    last: dict[str, str] = {}
    for _, g in games_sorted.iterrows():
        last[g["home_team"]] = g["game_date"]
        last[g["away_team"]] = g["game_date"]
    return last


def _rest_days(last_date_str: str | None, commence_time: str) -> int | None:
    if not last_date_str:
        return None
    last_date = dt.date.fromisoformat(last_date_str[:10])
    commence_date = dt.datetime.fromisoformat(commence_time.replace("Z", "+00:00")).date()
    return (commence_date - last_date).days


def event_to_game_record(sport: str, event: dict, last_game_dates: dict[str, str]) -> GameRecord:
    commence_time = event["commence_time"]
    home_team, away_team = event["home_team"], event["away_team"]
    return GameRecord(
        game_id=game_id_from_odds_event(sport, event),
        sport=sport,
        season=dt.datetime.fromisoformat(commence_time.replace("Z", "+00:00")).year,
        game_date=commence_time,
        home_team=home_team,
        away_team=away_team,
        home_rest_days=_rest_days(last_game_dates.get(home_team), commence_time),
        away_rest_days=_rest_days(last_game_dates.get(away_team), commence_time),
    )


def games_today_dataframe(records: list[GameRecord]) -> pd.DataFrame:
    rows = []
    for g in records:
        d = asdict(g)
        d["is_final"] = int(d["is_final"])
        d["neutral_site"] = int(d["neutral_site"])
        d["is_dome"] = int(d["is_dome"])
        rows.append(d)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Odds selection
# --------------------------------------------------------------------------- #


def pick_preferred_snapshot(
    snapshots: list[OddsSnapshot], market: str, preferred_books: list[str]
) -> OddsSnapshot | None:
    """Picks one book's line per market, preferring sharp/reference books
    first (config order — Pinnacle by default), falling back to whatever
    book is available so a thin market doesn't just get dropped."""
    candidates = [s for s in snapshots if s.market == market]
    if not candidates:
        return None
    by_book = {s.book: s for s in candidates}
    for book in preferred_books:
        if book in by_book:
            return by_book[book]
    return candidates[0]


# --------------------------------------------------------------------------- #
# Edge evaluation for one game, across all three markets
# --------------------------------------------------------------------------- #


def evaluate_game_edges(
    sport: str,
    game_id: str,
    home_team: str,
    away_team: str,
    commence_time: str,
    model_prob_home: float,
    model_margin: float,
    model_total: float,
    snapshots: list[OddsSnapshot],
    sigma_margin: float,
    sigma_total: float,
    min_edge: float,
    preferred_books: list[str],
) -> list[dict]:
    """Returns zero or more flagged-bet dicts (one per market that clears
    the edge threshold on either side)."""
    flags: list[dict] = []

    ml = pick_preferred_snapshot(snapshots, "moneyline", preferred_books)
    if ml and ml.home_price is not None and ml.away_price is not None:
        edge_home, dv = compute_edge(model_prob_home, ml.home_price, ml.away_price)
        if edge_home >= min_edge:
            flags.append(
                dict(
                    market="moneyline", side="home", price=ml.home_price, point=None,
                    model_prob=model_prob_home, market_prob=dv.prob_a, edge=edge_home, book=ml.book,
                    market_home_price=ml.home_price, market_away_price=ml.away_price, market_point=None,
                )
            )
        elif -edge_home >= min_edge:
            flags.append(
                dict(
                    market="moneyline", side="away", price=ml.away_price, point=None,
                    model_prob=1 - model_prob_home, market_prob=dv.prob_b, edge=-edge_home, book=ml.book,
                    market_home_price=ml.home_price, market_away_price=ml.away_price, market_point=None,
                )
            )

    sp = pick_preferred_snapshot(snapshots, "spread", preferred_books)
    if sp and sp.home_point is not None and sp.home_price is not None and sp.away_price is not None:
        prob_home_cover = margin_to_win_prob(model_margin + sp.home_point, sigma_margin)
        edge_home_cover, dv = compute_edge(prob_home_cover, sp.home_price, sp.away_price)
        if edge_home_cover >= min_edge:
            flags.append(
                dict(
                    market="spread", side="home", price=sp.home_price, point=sp.home_point,
                    model_prob=prob_home_cover, market_prob=dv.prob_a, edge=edge_home_cover, book=sp.book,
                    market_home_price=sp.home_price, market_away_price=sp.away_price, market_point=sp.home_point,
                )
            )
        elif -edge_home_cover >= min_edge:
            flags.append(
                dict(
                    market="spread", side="away", price=sp.away_price, point=sp.away_point,
                    model_prob=1 - prob_home_cover, market_prob=dv.prob_b, edge=-edge_home_cover, book=sp.book,
                    market_home_price=sp.home_price, market_away_price=sp.away_price, market_point=sp.home_point,
                )
            )

    tot = pick_preferred_snapshot(snapshots, "total", preferred_books)
    if tot and tot.home_point is not None and tot.home_price is not None and tot.away_price is not None:
        # by ingest_odds.parse_odds_api_event's convention, home_price/home_point
        # hold the Over side and away_price/away_point hold the Under side.
        prob_over = margin_to_win_prob(model_total - tot.home_point, sigma_total)
        edge_over, dv = compute_edge(prob_over, tot.home_price, tot.away_price)
        if edge_over >= min_edge:
            flags.append(
                dict(
                    market="total", side="over", price=tot.home_price, point=tot.home_point,
                    model_prob=prob_over, market_prob=dv.prob_a, edge=edge_over, book=tot.book,
                    market_home_price=tot.home_price, market_away_price=tot.away_price, market_point=tot.home_point,
                )
            )
        elif -edge_over >= min_edge:
            flags.append(
                dict(
                    market="total", side="under", price=tot.away_price, point=tot.away_point,
                    model_prob=1 - prob_over, market_prob=dv.prob_b, edge=-edge_over, book=tot.book,
                    market_home_price=tot.home_price, market_away_price=tot.away_price, market_point=tot.home_point,
                )
            )

    for f in flags:
        f.update(
            sport=sport, game_id=game_id, home_team=home_team, away_team=away_team,
            commence_time=commence_time, model_margin=model_margin, model_total=model_total,
            model_prob_home=model_prob_home,
        )
    return flags


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #


def format_market_line(market: str, side: str, price: float, point: float | None) -> str:
    if market == "moneyline":
        return f"{'Home' if side == 'home' else 'Away'} {price:+.0f}"
    if market == "spread":
        return f"{'Home' if side == 'home' else 'Away'} {point:+.1f} ({price:+.0f})"
    return f"{'Over' if side == 'over' else 'Under'} {point:.1f} ({price:+.0f})"


def format_model_line(market: str, side: str, model_prob: float, model_margin: float, model_total: float) -> str:
    if market == "moneyline":
        return f"{model_prob:.1%} win prob"
    if market == "spread":
        return f"pred. margin {model_margin:+.1f} ({model_prob:.1%} cover prob)"
    return f"pred. total {model_total:.1f} ({model_prob:.1%} {side} prob)"


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def process_sport(conn, client: OddsAPIClient, sport: str, cfg: dict, bankroll: float) -> tuple[list[dict], str | None]:
    """Returns (flagged_bet_rows, skip_reason). skip_reason is None if the
    sport was fully processed (even if it produced zero flagged bets)."""
    try:
        events = fetch_todays_events(client, sport)
    except requests.exceptions.RequestException as e:
        return [], f"odds API request failed ({e})"

    if not events:
        return [], "no games scheduled today (out of season or no slate)"

    games_hist = load_games(conn, sport)
    stats_hist = load_team_game_stats(conn, sport)

    try:
        prod = train_production_models(games_hist, stats_hist, sport, cfg)
    except InsufficientHistoryError as e:
        return [], str(e)

    last_game_dates = _last_game_dates(games_hist.sort_values("game_date"))
    records = [event_to_game_record(sport, e, last_game_dates) for e in events]
    upsert_games(records, conn)  # required: predictions.game_id has a FK into games
    games_today_df = games_today_dataframe(records)

    live_feat_df = build_live_feature_rows(games_hist, stats_hist, games_today_df, sport, prod.elo_ratings)
    if live_feat_df.empty:
        return [], "could not build pre-game features for today's slate (insufficient team history)"

    live_feat_df = live_feat_df.assign(
        model_prob_home=prod.win_model.predict_proba(live_feat_df),
        model_margin=prod.margin_model.predict(live_feat_df),
        model_total=prod.total_model.predict(live_feat_df),
    )

    now_iso = dt.datetime.utcnow().isoformat()
    min_edge = cfg["edge_detection"]["min_edge_threshold"]
    preferred_books = cfg["odds_api"]["bookmakers"]

    all_flags: list[dict] = []
    for event in events:
        gid = game_id_from_odds_event(sport, event)
        row_match = live_feat_df[live_feat_df["game_id"] == gid]
        if row_match.empty:
            continue
        row = row_match.iloc[0]
        snapshots = parse_odds_api_event(sport, event, "live", now_iso)

        flags = evaluate_game_edges(
            sport, gid, row["home_team"], row["away_team"], event["commence_time"],
            float(row["model_prob_home"]), float(row["model_margin"]), float(row["model_total"]),
            snapshots, prod.sigma_margin, prod.sigma_total, min_edge, preferred_books,
        )

        for f in flags:
            kr = size_bet(f["model_prob"], f["price"], bankroll, cfg=cfg)
            f["stake"] = kr.stake
            f["kelly_fraction_used"] = kr.capped_fraction

            try:
                prediction_id = log_prediction(
                    game_id=gid, sport=sport, model_name=MODEL_NAME, model_version=MODEL_VERSION,
                    market=f["market"], side=f["side"], game_start_at=event["commence_time"],
                    model_prob_home=f["model_prob_home"], model_margin=f["model_margin"], model_total=f["model_total"],
                    market_home_price=f["market_home_price"], market_away_price=f["market_away_price"],
                    market_point=f["market_point"], market_book=f["book"],
                    market_devigged_prob_home=f["market_prob"] if f["side"] in ("home", "over") else 1 - f["market_prob"],
                    edge=f["edge"], flagged=True, conn=conn, _now_override=now_iso,
                )
                f["already_logged"] = False
            except PreGameLockViolation as e:
                print(f"  SKIPPED (guardrail): {e}")
                continue
            except sqlite3.IntegrityError:
                # UNIQUE constraint on prediction_id: this exact
                # (game, model, market, side) was already logged earlier
                # today (e.g. daily_report.py or the dashboard's "Today's
                # Bets" tab ran once already). Not an error — re-running
                # the same day's report should be idempotent, not crash.
                # We do NOT re-log (the guardrail is append-only on
                # purpose); we just surface the same prediction_id so the
                # flag still shows up in this run's output.
                prediction_id = make_prediction_id(gid, MODEL_NAME, MODEL_VERSION, f["market"], f["side"])
                f["already_logged"] = True
            f["prediction_id"] = prediction_id

        all_flags.extend(flags)

    return all_flags, None


def flags_to_dataframe(all_flags: list[dict]) -> pd.DataFrame:
    """Shared by the console report (print_report, below) and
    dashboard/app.py's "Today's Bets" tab, so both render exactly the same
    numbers from exactly the same underlying flag dicts — never two
    independently-formatted copies that could drift apart."""
    if not all_flags:
        return pd.DataFrame(
            columns=["sport", "matchup", "kickoff_utc", "market", "side", "market_line", "model_line", "edge_pct", "suggested_stake", "book"]
        )
    report_rows = [
        {
            "sport": f["sport"],
            "matchup": f"{f['away_team']} @ {f['home_team']}",
            "kickoff_utc": f["commence_time"],
            "market": f["market"],
            "side": f["side"],
            "market_line": format_market_line(f["market"], f["side"], f["price"], f["point"]),
            "model_line": format_model_line(f["market"], f["side"], f["model_prob"], f["model_margin"], f["model_total"]),
            "edge_pct": f["edge"],
            "suggested_stake": f["stake"],
            "book": f["book"],
        }
        for f in all_flags
    ]
    return pd.DataFrame(report_rows).sort_values("edge_pct", ascending=False).reset_index(drop=True)


def print_report(all_flags: list[dict], skipped: dict[str, str], threshold: float) -> pd.DataFrame:
    print(f"\n{'=' * 78}\nDAILY EDGE REPORT — {dt.date.today().isoformat()} (UTC slate)\n{'=' * 78}")

    for sport, reason in skipped.items():
        print(f"{sport}: SKIPPED — {reason}")

    df = flags_to_dataframe(all_flags)
    if df.empty:
        print(
            f"\nNo games cleared the {threshold:.1%} edge threshold today across the sports checked. "
            "No bets are being suggested — the bar is not lowered to manufacture picks."
        )
        return df

    display_df = df.copy()
    display_df["edge_pct"] = display_df["edge_pct"].map(lambda x: f"{x:+.1%}")
    display_df["suggested_stake"] = display_df["suggested_stake"].map(lambda x: f"${x:,.2f}")
    print(f"\n{len(df)} game/market combinations cleared the {threshold:.1%} edge threshold:\n")
    print(display_df.to_string(index=False))

    return df


def run_daily_report(
    cfg: dict | None = None,
    edge_threshold: float | None = None,
    bankroll_override: float | None = None,
    sports: tuple[str, ...] = SPORTS,
    progress_cb=None,
) -> dict:
    """Runs the full daily edge report and returns its results as data,
    with no printing — shared by main() (below, for the CLI) and
    dashboard/app.py's "Today's Bets" tab, so both drive the exact same
    logic and neither can silently drift from the other.

    `progress_cb(sport, message)`, if given, is called once per sport as
    it's processed — the dashboard uses this to update a spinner/status
    line during what can be a slow (model-training) operation; the CLI
    doesn't need it (it prints directly via process_sport/print_report
    instead, see main()).

    Returns a dict: {flags: list[dict], skipped: dict[str,str],
    bankroll_stats: BankrollStats, threshold: float, min_sig_n: int}.
    Raises RuntimeError if no ODDS_API_KEY is configured (nothing to do
    without live odds) — callers decide how to present that.
    """
    cfg = cfg or load_config()
    if edge_threshold is not None:
        cfg = {**cfg, "edge_detection": {**cfg["edge_detection"], "min_edge_threshold": edge_threshold}}
    threshold = cfg["edge_detection"]["min_edge_threshold"]
    min_sig_n = cfg["edge_detection"]["min_sample_size_for_significance"]

    client = OddsAPIClient(cfg=cfg)  # raises RuntimeError if ODDS_API_KEY isn't set

    with connect() as conn:
        ledger = bet_ledger_all(conn)
        starting_bankroll = cfg["bankroll"]["starting_bankroll"]
        bankroll_stats = compute_bankroll_stats(ledger, starting_bankroll)
        current_bankroll = bankroll_override if bankroll_override is not None else bankroll_stats.ending_bankroll

        all_flags: list[dict] = []
        skipped: dict[str, str] = {}
        for sport in sports:
            if progress_cb:
                progress_cb(sport, f"Training {sport} production models and pulling today's odds...")
            flags, skip_reason = process_sport(conn, client, sport, cfg, current_bankroll)
            if skip_reason:
                skipped[sport] = skip_reason
            all_flags.extend(flags)

    return {
        "flags": all_flags,
        "skipped": skipped,
        "bankroll_stats": bankroll_stats,
        "threshold": threshold,
        "min_sig_n": min_sig_n,
    }


def main():
    parser = argparse.ArgumentParser(description="Daily pre-game edge report for NFL/NCAAF/NBA.")
    parser.add_argument("--csv", default=None, help="Optional path to also write the report as CSV.")
    parser.add_argument("--edge-threshold", type=float, default=None, help="Override config's min_edge_threshold.")
    parser.add_argument("--bankroll", type=float, default=None, help="Override the bankroll used for Kelly sizing.")
    args = parser.parse_args()

    cfg = load_config()
    min_sig_n = cfg["edge_detection"]["min_sample_size_for_significance"]

    def _cli_progress(sport, message):
        print(f"\nChecking {sport}... ({message})")

    try:
        result = run_daily_report(
            cfg, edge_threshold=args.edge_threshold, bankroll_override=args.bankroll, progress_cb=_cli_progress
        )
    except RuntimeError as e:
        print(e)
        print("Cannot generate a daily report without live pre-game odds. Exiting.")
        sys.exit(1)

    print(bankroll_headline(result["bankroll_stats"], min_sig_n))
    warn = small_sample_warning(result["bankroll_stats"].n_bets, min_sig_n)
    if warn:
        print(f"NOTE: {warn}")

    for sport, reason in result["skipped"].items():
        print(f"{sport}: {reason}")

    report_df = print_report(result["flags"], result["skipped"], result["threshold"])

    if args.csv and not report_df.empty:
        report_df.to_csv(args.csv, index=False)
        print(f"\nWrote {len(report_df)} rows to {args.csv}")

    print(f"\n{'=' * 78}\nDISCLAIMERS\n{'=' * 78}")
    print(full_disclaimer_block())


if __name__ == "__main__":
    main()

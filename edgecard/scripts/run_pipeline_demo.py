"""End-to-end demo: trains Elo + GBM per sport on the synthetic data (run
scripts/generate_sample_data.py first), walk-forward backtests, de-vigs the
synthetic closing lines, flags edges, logs predictions through the
guardrails module, simulates a bet ledger with fractional-Kelly sizing,
records CLV, and prints a full report — the same computations the dashboard
renders, run here so you can see the pipeline work without Streamlit.

Remember: this runs against FABRICATED data (see generate_sample_data.py's
docstring). Nothing printed here is evidence of real-world edge.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from data_pipeline.config import load_config
from data_pipeline.db import connect
from data_pipeline.queries import load_games, load_team_game_stats, load_odds_snapshots
from edge.devig import devig, american_to_decimal
from edge.edge_detection import compute_edge
from edge.clv_tracker import record_clv, summarize_clv
from bankroll.kelly import size_bet
from bankroll.bankroll_tracker import compute_bankroll_stats, bankroll_headline
from bankroll.monte_carlo import simulate_bankroll_paths
from guardrails.prediction_log import log_prediction, PreGameLockViolation
from guardrails.disclaimers import full_disclaimer_block, small_sample_warning
from models.features import build_feature_frame, feature_columns, select_populated_feature_columns
from models.backtest import run_walk_forward_elo, run_walk_forward_gbm_classifier

DEMO_MIN_TRAIN_GAMES = 250
DEMO_RETRAIN_EVERY = 60
KICKOFF_HOUR = 18


def load_odds(conn, sport: str, market: str, snapshot_type: str) -> pd.DataFrame:
    return load_odds_snapshots(conn, sport, market, snapshot_type, book="synthetic_book")


def run_sport(conn, sport: str, cfg: dict) -> dict:
    print(f"\n{'=' * 70}\n{sport}\n{'=' * 70}")

    games = load_games(conn, sport)
    stats = load_team_game_stats(conn, sport)
    games_sorted = games.sort_values("game_date").reset_index(drop=True)

    elo_df = run_walk_forward_elo(games_sorted).merge(
        games_sorted[["game_id", "home_team", "away_team"]], on="game_id"
    )
    elo_by_game = {
        row["game_id"]: {row["home_team"]: row["home_elo_pre"], row["away_team"]: row["away_elo_pre"]}
        for _, row in elo_df.iterrows()
    }

    feat_df = build_feature_frame(games_sorted, stats, sport, elo_ratings_by_date=elo_by_game)
    all_feat_cols = feature_columns(feat_df)
    # Drop columns that are entirely (or almost entirely) missing — e.g. PFF
    # grades, which this synthetic generator never populates because PFF
    # requires a paid subscription (see ingest_advanced_stats.py). Requiring
    # a fully-null column in dropna() would silently drop every row.
    feat_cols = select_populated_feature_columns(feat_df, all_feat_cols)
    dropped = sorted(set(all_feat_cols) - set(feat_cols))
    if dropped:
        print(f"Dropping mostly-missing feature columns (not populated in this data source): {dropped}")

    model_df = feat_df.dropna(subset=feat_cols + ["home_win"]).reset_index(drop=True)
    model_df = model_df.sort_values("game_date").reset_index(drop=True)

    print(f"Games: {len(games_sorted)} total, {len(model_df)} usable after rolling-feature warmup dropna")
    print(f"Features used: {feat_cols}")

    if len(model_df) <= DEMO_MIN_TRAIN_GAMES + DEMO_RETRAIN_EVERY:
        print(f"Not enough usable games for a walk-forward backtest in this demo run; skipping {sport}.")
        return {}

    wf = run_walk_forward_gbm_classifier(
        model_df, feat_cols, "home_win", DEMO_MIN_TRAIN_GAMES, DEMO_RETRAIN_EVERY
    )
    print(f"Walk-forward folds: {wf.n_folds}, out-of-sample predictions: {len(wf.predictions)}")
    if wf.calibration:
        print(wf.calibration.summary())

    close_ml = load_odds(conn, sport, "moneyline", "close").set_index("game_id")
    open_ml = load_odds(conn, sport, "moneyline", "open").set_index("game_id")

    preds = wf.predictions.merge(games_sorted[["game_id", "home_team", "away_team"]], on="game_id")

    min_edge = cfg["edge_detection"]["min_edge_threshold"]
    starting_bankroll = cfg["bankroll"]["starting_bankroll"]
    bankroll = starting_bankroll

    ledger_rows = []
    model_name, model_version = "xgb_gbm", f"v1_{sport.lower()}"
    n_logged, n_flagged = 0, 0

    for _, row in preds.sort_values("game_date").iterrows():
        gid = row["game_id"]
        if gid not in open_ml.index or gid not in close_ml.index:
            continue
        o = open_ml.loc[gid]
        c = close_ml.loc[gid]
        if pd.isna(o["home_price"]) or pd.isna(o["away_price"]):
            continue

        model_prob_home = float(row["y_pred_prob"])
        edge_home, dv_open = compute_edge(model_prob_home, o["home_price"], o["away_price"])

        if edge_home >= min_edge:
            side, price_side, price_other, model_prob_side = "home", o["home_price"], o["away_price"], model_prob_home
            edge = edge_home
        elif -edge_home >= min_edge:
            side, price_side, price_other, model_prob_side = "away", o["away_price"], o["home_price"], 1 - model_prob_home
            edge = -edge_home
        else:
            continue

        n_flagged += 1
        game_date = dt.datetime.fromisoformat(row["game_date"])
        game_start_at = game_date.replace(hour=KICKOFF_HOUR).isoformat()
        predicted_at = o["captured_at"]

        try:
            prediction_id = log_prediction(
                game_id=gid,
                sport=sport,
                model_name=model_name,
                model_version=model_version,
                market="moneyline",
                side=side,
                game_start_at=game_start_at,
                model_prob_home=model_prob_home,
                market_home_price=o["home_price"],
                market_away_price=o["away_price"],
                market_devigged_prob_home=dv_open.prob_a,
                edge=edge,
                flagged=True,
                conn=conn,
                _now_override=predicted_at,
            )
        except PreGameLockViolation:
            continue
        n_logged += 1

        home_price_close, away_price_close = c["home_price"], c["away_price"]
        clv_home_price = home_price_close if side == "home" else away_price_close
        clv_other_price = away_price_close if side == "home" else home_price_close
        record_clv(prediction_id, price_side, None, clv_home_price, clv_other_price, conn=conn)

        kr = size_bet(model_prob_side, price_side, bankroll, cfg=cfg)
        home_won = bool(row["y_true"])
        side_won = home_won if side == "home" else (not home_won)

        net_odds = american_to_decimal(price_side) - 1.0
        payout = kr.stake * net_odds if side_won else -kr.stake
        bankroll_before = bankroll
        bankroll = max(bankroll + payout, 0.0)

        conn.execute(
            """INSERT INTO bet_ledger (prediction_id, placed_at, stake, kelly_fraction_used,
               bankroll_before, price, result, settled_at, payout, bankroll_after)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                prediction_id, predicted_at, kr.stake, kr.capped_fraction, bankroll_before,
                price_side, "win" if side_won else "loss", game_start_at, payout, bankroll,
            ),
        )
        ledger_rows.append(
            dict(placed_at=predicted_at, stake=kr.stake, payout=payout, result="win" if side_won else "loss")
        )

    print(f"Flagged {n_flagged} edges >= {min_edge:.1%}, logged {n_logged} predictions.")

    ledger_df = pd.DataFrame(ledger_rows)
    if not ledger_df.empty:
        stats_out = compute_bankroll_stats(ledger_df, starting_bankroll)
        print(bankroll_headline(stats_out, cfg["edge_detection"]["min_sample_size_for_significance"]))
        if stats_out.roi_pct > 0.05:
            print(
                "  NOTE: this ROI is against FABRICATED synthetic data (see generate_sample_data.py) "
                "and reflects the generator's noise structure, not a real, sustainable market edge. "
                "No real sportsbook lets an account flag and win thousands of bets at a multi-percent "
                "CLV edge without limiting or banning it — treat this only as a pipeline smoke test."
            )

        clv_rows = pd.read_sql_query(
            """SELECT c.clv_prob_pct FROM clv_records c
               JOIN predictions p ON p.prediction_id = c.prediction_id
               WHERE p.sport = ?""",
            conn,
            params=(sport,),
        )
        clv_summary = summarize_clv(clv_rows["clv_prob_pct"], cfg)
        print(clv_summary.headline())
    else:
        stats_out = None
        clv_summary = None
        print("No settled bets this run.")

    return {"sport": sport, "n_flagged": n_flagged, "bankroll_stats": stats_out, "clv_summary": clv_summary}


def main():
    print(
        "NOTE: this demo runs against synthetic, fabricated data generated by "
        "scripts/generate_sample_data.py so the pipeline can be exercised end to end without "
        "API keys. All 'edge', ROI, and CLV numbers below are artifacts of that synthetic "
        "generator, not evidence this system finds real edges in real markets.\n"
    )
    cfg = load_config()
    results = []
    with connect() as conn:
        for sport in ("NFL", "NCAAF", "NBA"):
            results.append(run_sport(conn, sport, cfg))

    print(f"\n{'=' * 70}\nMonte Carlo reality check (canonical example)\n{'=' * 70}")
    mc = simulate_bankroll_paths(
        true_win_prob=0.55, price=-110, stake_fraction=cfg["kelly"]["max_bet_pct_of_bankroll"], cfg=cfg, seed=7
    )
    print(mc.headline())

    print(f"\n{'=' * 70}\nDISCLAIMERS\n{'=' * 70}")
    print(full_disclaimer_block())


if __name__ == "__main__":
    main()

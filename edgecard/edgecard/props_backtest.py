"""Out-of-sample check of the NFL props model against real player outcomes.

No free source has historical prop PRICES, so this cannot measure betting
edge on props. What it can measure honestly:
  - calibration of the simulated distributions (PIT histogram: the share of
    actual results falling in each decile of our predicted distribution
    should be ~10% each), and
  - Brier score of P(over L) at fixed common lines vs a naive baseline
    (the player's recent average with a textbook spread).
Game script comes from the walk-forward game backtest (out of sample).
"""
from __future__ import annotations

import pickle

import numpy as np
import pandas as pd
from scipy.stats import norm, poisson

from edgecard import store
from models.distributions import DiscreteDist
from models.nfl_props import statuses_from_injury_report, team_volume_params, team_week_totals, project_team
from sim.nfl_sim import simulate_game

LINES = {"receptions": [2.5, 3.5, 4.5, 5.5], "rec_yds": [24.5, 39.5, 54.5, 69.5], "rush_yds": [29.5, 49.5, 69.5],
         "pass_yds": [199.5, 224.5, 249.5, 274.5], "pass_cmp": [18.5, 21.5, 24.5], "rush_att": [9.5, 14.5, 17.5]}
ACTUAL_COL = {"receptions": "receptions", "rec_yds": "receiving_yards", "rush_yds": "rushing_yards",
              "pass_yds": "passing_yards", "pass_cmp": "completions", "rush_att": "carries"}


def run_props_backtest(seasons=(2024, 2025), n_sims: int = 3000, min_week: int = 4, max_games: int | None = None) -> dict:
    from data_pipeline.sources.nflverse_hist import load

    art = pickle.load(open(store.path("models", "nfl_game.pkl"), "rb"))
    gm = art["model"]
    oos = pd.read_parquet(store.path("reports", "backtest_nfl_oos.parquet"))
    games = load("nfl_games")
    pw = load("nfl_player_weeks")
    pw = pw[pw["season_type"] == "REG"] if "season_type" in pw else pw
    pw = pw.merge(team_week_totals(pw), on=["team", "season", "week"])
    tg = load("nfl_team_games")
    inj = load("nfl_injuries")
    snaps = load("nfl_snaps")
    g = games[games["season"].isin(seasons) & (games["week"] >= min_week) & (games["game_type"] == "REG")]
    g = g.merge(oos[["game_id", "pred_margin", "pred_total"]], on="game_id")
    if max_games:
        g = g.head(max_games)
    rows = []
    for _, r in g.iterrows():
        s, w = int(r["season"]), int(r["week"])
        H = project_team(pw, r["home_team"], (s, w), *team_volume_params(tg, r["home_team"], s, w),
                         statuses=statuses_from_injury_report(inj, r["home_team"], s, w))
        A = project_team(pw, r["away_team"], (s, w), *team_volume_params(tg, r["away_team"], s, w),
                         statuses=statuses_from_injury_report(inj, r["away_team"], s, w))
        md = DiscreteDist.build(r["pred_margin"], float(gm.sigma_margin(r["pred_total"])), gm.kw_margin)
        sim = simulate_game(md, r["pred_total"], float(gm.sigma_total(r["pred_total"])), gm.joint.rho_fav, H, A, n=n_sims, seed=s * 100 + w)
        actual = pw[(pw["season"] == s) & (pw["week"] == w) & pw["team"].isin([r["home_team"], r["away_team"]])]
        act = {str(x["player"]): x for _, x in actual.iterrows()}
        # everyone who took an offensive snap played, even with no stat row
        # (nflverse weekly stats omit players with zero touches/targets)
        sn = snaps[(snaps["game_id"] == r["game_id"]) & (snaps["offense_snaps"] > 0)]
        zero = pd.Series({c: 0.0 for c in ACTUAL_COL.values()} | {"targets": 0.0})
        for nm in sn["player"].astype(str):
            act.setdefault(nm, zero)
        for (player, market), arr in sim.stats.items():
            if market not in LINES or player not in act:
                continue
            a = act[player]
            y = float(a[ACTUAL_COL[market]])
            # recent average baseline (same information window)
            prev = pw[(pw["player"] == player) & ((pw["season"] < s) | ((pw["season"] == s) & (pw["week"] < w)))].tail(6)
            base_mean = float(prev[ACTUAL_COL[market]].mean()) if len(prev) else np.nan
            u = np.random.default_rng(0).uniform()
            pit = float((arr < y).mean() + u * (arr == y).mean())
            rec = {"season": s, "week": w, "player": player, "market": market, "actual": y, "pred_mean": float(arr.mean()),
                   "base_mean": base_mean, "pit": pit}
            for L in LINES[market]:
                rec[f"p_over_{L}"] = float((arr > L).mean())
                if not np.isnan(base_mean):
                    if market in ("receptions", "pass_cmp", "rush_att"):
                        rec[f"b_over_{L}"] = float(1 - poisson.cdf(np.floor(L), max(base_mean, 0.05)))
                    else:
                        rec[f"b_over_{L}"] = float(1 - norm.cdf(L, base_mean, max(0.75 * base_mean, 8.0)))
                rec[f"y_over_{L}"] = float(y > L)
            rows.append(rec)
    df = pd.DataFrame(rows)
    out = {"n_player_games": int(len(df)), "seasons": list(seasons), "markets": {}}
    for m, d in df.groupby("market"):
        pit_hist = np.histogram(d["pit"], bins=10, range=(0, 1))[0] / len(d)
        mb, bb, nn = [], [], 0
        for L in LINES[m]:
            dd = d.dropna(subset=[f"b_over_{L}"])
            mb.append(float(((dd[f"p_over_{L}"] - dd[f"y_over_{L}"]) ** 2).mean()))
            bb.append(float(((dd[f"b_over_{L}"] - dd[f"y_over_{L}"]) ** 2).mean()))
            nn += len(dd)
        out["markets"][m] = {"n": int(len(d)), "pit_deciles": [round(float(x), 3) for x in pit_hist],
                             "mean_pred": float(d["pred_mean"].mean()), "mean_actual": float(d["actual"].mean()),
                             "brier_model": float(np.mean(mb)), "brier_naive": float(np.mean(bb)),
                             "model_beats_naive": bool(np.mean(mb) < np.mean(bb))}
    store.write_json(out, "reports", "backtest_nfl_props.json")
    return out

"""NBA game model: point-in-time features, walk-forward backtest, live means.

Same machinery as the NFL (models/game_model.py): gradient-boosted mean,
fitted variance, discrete distribution, market-anchored calibration whose
model weight is 0 unless earned out of sample. Feature groups are tested
one at a time against the base set, exactly like the NFL ablation.

Data (free, verified reachable from GitHub runners): ESPN scoreboards for
scores + lines, pbpstats.com for possessions (ratings, pace).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import pickle
from collections import defaultdict

import numpy as np
import pandas as pd

from data_pipeline.schedule_features import game_level_schedule_features
from edgecard import store
from models.distributions import MARGIN_SUPPORT, KeyWeights
from models.game_model import Calibrators, GameModel, MARKETS

HALF_LIFE = 10.0
CARRY = 0.7
FORM = ["pts_for", "pts_against", "ortg", "drtg", "pace", "fg3a_rate", "ftr", "tov_rate"]
PRIORS = {"pts_for": 112.0, "pts_against": 112.0, "ortg": 113.0, "drtg": 113.0, "pace": 99.0,
          "fg3a_rate": 0.38, "ftr": 0.25, "tov_rate": 0.13}

NBA_GROUPS = {
    "base": ["elo_diff", "elo_prob", "home_field", "f_pts_net_diff", "f_pts_sum"],
    "efficiency": ["f_net_rtg_diff", "f_ortg_h_vs_drtg_a", "f_ortg_a_vs_drtg_h", "f_pace_sum"],
    "style": ["f_fg3a_rate_sum", "f_ftr_diff", "f_tov_diff"],
    "fatigue": ["sched_rest_diff", "sched_b2b_diff", "sched_3in4_diff", "sched_travel_diff", "sched_tz_away_abs",
                "sched_prev_ot_diff", "sched_road_trip_away"],
    "altitude": ["sched_altitude_ft"],
    "motivation": ["tank_h", "tank_a", "playoff_game", "revenge_h", "revenge_a", "late_season"],
    "h2h": ["h2h_resid_margin"],
}


def nba_cols(groups):
    out = []
    for g in groups:
        out += NBA_GROUPS[g]
    return out


def _ewma_get(state, team, season, season_of):
    if team not in state:
        return dict(PRIORS)
    if season_of.get(team) != season:
        state[team] = {k: CARRY * v + (1 - CARRY) * PRIORS[k] for k, v in state[team].items()}
        season_of[team] = season
    return dict(state[team])


def build_nba_features(games: pd.DataFrame, team_games: pd.DataFrame | None) -> pd.DataFrame:
    g = games.sort_values("kickoff").reset_index(drop=True).copy()
    g["margin"] = g["home_score"] - g["away_score"]
    g["total_pts"] = g["home_score"] + g["away_score"]
    g["is_final"] = g["home_score"].notna()
    tg = {}
    if team_games is not None and len(team_games):
        t = team_games.copy()
        t["fg3a_rate"] = t["fg3a"] / (t["fg3a"] + t["fg2a"]).replace(0, np.nan)
        t["ftr"] = t["fta"] / (t["fg3a"] + t["fg2a"]).replace(0, np.nan)
        t["tov_rate"] = t["tov"] / t["off_poss"].replace(0, np.nan)
        for _, r in t.iterrows():
            tg[(str(r["date"])[:10], r["team"])] = r
    alpha = 1 - 0.5 ** (1 / HALF_LIFE)
    state, season_of = {}, {}
    elo = defaultdict(lambda: 1500.0)
    elo_season = {}
    record = defaultdict(lambda: [0, 0])
    last_meet = {}
    h2h = defaultdict(list)
    rows = []
    for _, r in g.iterrows():
        h, a, s = r["home_team"], r["away_team"], int(r["season"])
        for t_ in (h, a):
            if elo_season.get(t_) is not None and elo_season[t_] != s:
                elo[t_] = 0.75 * elo[t_] + 0.25 * 1500
            elo_season[t_] = s
        fh, fa = _ewma_get(state, h, s, season_of), _ewma_get(state, a, s, season_of)
        hfa = 0 if r["neutral_site"] else 70.0
        ed = elo[h] + hfa - elo[a]
        wh, lh = record[(h, s)]
        wa, la = record[(a, s)]
        gp_h, gp_a = wh + lh, wa + la
        is_reg = r["game_type"] == "REG"
        lm = last_meet.get(frozenset((h, a)))
        hh = h2h.get((h, a), []) + [-x for x in h2h.get((a, h), [])]
        rows.append({
            "game_id": r["game_id"], "season": s, "week": 0, "game_type": r["game_type"], "kickoff": r["kickoff"],
            "game_date": r["game_date"], "home_team": h, "away_team": a, "neutral_site": r["neutral_site"],
            "home_field": 0.0 if r["neutral_site"] else 1.0, "elo_diff": ed, "elo_prob": 1 / (1 + 10 ** (-ed / 400)),
            "f_pts_net_diff": (fh["pts_for"] - fh["pts_against"]) - (fa["pts_for"] - fa["pts_against"]),
            "f_pts_sum": fh["pts_for"] + fh["pts_against"] + fa["pts_for"] + fa["pts_against"],
            "f_net_rtg_diff": (fh["ortg"] - fh["drtg"]) - (fa["ortg"] - fa["drtg"]),
            "f_ortg_h_vs_drtg_a": fh["ortg"] + fa["drtg"], "f_ortg_a_vs_drtg_h": fa["ortg"] + fh["drtg"],
            "f_pace_sum": fh["pace"] + fa["pace"], "f_fg3a_rate_sum": fh["fg3a_rate"] + fa["fg3a_rate"],
            "f_ftr_diff": fh["ftr"] - fa["ftr"], "f_tov_diff": fh["tov_rate"] - fa["tov_rate"],
            "tank_h": float(is_reg and gp_h >= 55 and wh / max(gp_h, 1) < 0.35),
            "tank_a": float(is_reg and gp_a >= 55 and wa / max(gp_a, 1) < 0.35),
            "playoff_game": float(not is_reg), "late_season": float(is_reg and min(gp_h, gp_a) >= 70),
            "revenge_h": float(lm is not None and lm == a), "revenge_a": float(lm is not None and lm == h),
            "h2h_resid_margin": float(np.mean(hh[-3:])) if hh else 0.0,
            "spread_line": -r["home_spread"] if pd.notna(r.get("home_spread")) else np.nan,
            "total_line": r.get("total_line"), "home_moneyline": r.get("home_moneyline"),
            "away_moneyline": r.get("away_moneyline"), "home_spread_odds": r.get("home_spread_odds"),
            "away_spread_odds": r.get("away_spread_odds"), "over_odds": r.get("over_odds"),
            "under_odds": r.get("under_odds"), "margin": r["margin"], "total_pts": r["total_pts"],
            "is_final": bool(r["is_final"]), "overtime": r.get("overtime", 0),
        })
        if not r["is_final"]:
            continue
        m = float(r["margin"])
        for team, is_home in ((h, 1), (a, 0)):
            pf = r["home_score"] if is_home else r["away_score"]
            pa = r["away_score"] if is_home else r["home_score"]
            obs = {"pts_for": pf, "pts_against": pa}
            b = tg.get((r["game_date"], team))
            if b is not None and pd.notna(b.get("ortg")):
                obs.update({k: float(b[k]) for k in ("ortg", "drtg", "pace", "fg3a_rate", "ftr", "tov_rate") if pd.notna(b.get(k))})
            cur = state.setdefault(team, dict(PRIORS))
            for k, v in obs.items():
                cur[k] += alpha * (float(v) - cur[k])
            season_of[team] = s
        exp = 1 / (1 + 10 ** (-ed / 400))
        act = 1.0 if m > 0 else 0.0
        mult = math.log(abs(m) + 1) * (2.2 / ((ed if m > 0 else -ed) * 0.001 + 2.2))
        d = 20.0 * max(mult, 0.1) * (act - exp)
        elo[h] += d
        elo[a] -= d
        if is_reg:
            record[(h, s)][0 if m > 0 else 1] += 1
            record[(a, s)][0 if m < 0 else 1] += 1
        last_meet[frozenset((h, a))] = h if m > 0 else a
        h2h[(h, a)].append(m - ed / 28.0)
    df = pd.DataFrame(rows)
    sched = game_level_schedule_features(g[["game_id", "game_date", "home_team", "away_team", "overtime"]], "NBA")
    return df.merge(sched, on="game_id", how="left")


def load_nba_frame() -> pd.DataFrame:
    g = pd.read_parquet(store.history_path("nba_games"))
    tp = store.history_path("nba_team_games")
    tg = pd.read_parquet(tp) if tp.exists() else None
    return build_nba_features(g, tg)


def run_nba_backtest(quick: bool = False) -> dict:
    from edgecard import backtest as bt

    frame = load_nba_frame()
    latest = int(frame.loc[frame["is_final"], "season"].max())
    first_test = latest - (1 if quick else 3)
    print(f"NBA backtest: test seasons {first_test}-{latest} ({frame['is_final'].sum()} final games)")
    base = nba_cols(["base"])
    b_oos = bt.walk_forward(frame, base, first_test, latest, n_estimators=150)
    b_ll, b_seasons = bt._mean_model_ll(b_oos)
    abl = {"base": {"model_logloss": b_ll}, "groups": {}}
    for grp in [g for g in NBA_GROUPS if g != "base"]:
        oos = bt.walk_forward(frame, base + nba_cols([grp]), first_test, latest, n_estimators=150)
        ll, seasons = bt._mean_model_ll(oos)
        wins = sum(1 for s_ in seasons if seasons[s_] < b_seasons.get(s_, np.inf))
        keep = bool(ll < b_ll and wins >= len(seasons) / 2)
        abl["groups"][grp] = {"model_logloss": ll, "delta_model": ll - b_ll, "seasons_improved": wins,
                              "seasons": len(seasons), "keep": keep, "features": NBA_GROUPS[grp],
                              "delta_final": 0.0, "delta_rmse": 0.0}
        print(f"  ablation {grp:<12} Δmodel_ll={ll - b_ll:+.5f} improved {wins}/{len(seasons)} -> {'KEEP' if keep else 'drop'}")
    abl["kept"] = [g for g, v in abl["groups"].items() if v["keep"]]
    abl["dropped"] = [g for g, v in abl["groups"].items() if not v["keep"]]
    abl["not_tested"] = {"cohesion / role conflict": "needs lineup on/off data at scale (stats.nba.com is blocked from "
                                                     "cloud runners); pbpstats lineups can be added later",
                         "star rest-risk": "needs player availability history"}
    groups = ["base"] + abl["kept"]
    cols = nba_cols(groups)
    oos = bt.walk_forward(frame, cols, first_test, latest)
    summ = bt.summarize(oos, frame)
    verdicts = bt._verdicts(summ)
    resid = pd.DataFrame({"resid_margin": oos["margin"] - oos["pred_margin"], "resid_total": oos["total_pts"] - oos["pred_total"],
                          "pred_margin": oos["pred_margin"], "pred_total": oos["pred_total"],
                          "margin": oos["margin"], "total_pts": oos["total_pts"]})
    gm = GameModel(cols).fit(frame[frame["is_final"]], oos_resid=resid)
    gm.kw_margin = KeyWeights.fit(resid["margin"], MARGIN_SUPPORT, center=resid["pred_margin"],
                                  sigma=float(resid["resid_margin"].std()), clip=(0.3, 2.0))
    cal = Calibrators.fit(oos)
    with open(store.path("models", "nba_game.pkl"), "wb") as f:
        pickle.dump({"model": gm, "calibrators": cal, "groups": groups, "trained_at": dt.datetime.utcnow().isoformat(),
                     "trained_through": str(frame.loc[frame["is_final"], "game_date"].max())}, f)
    rep = {"league": "NBA", "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
           "test_seasons": [first_test, latest], "n_games_oos": int(len(oos)), "feature_groups_used": groups,
           "ablation": abl, "summary": summ, "stack_coefficients": cal.stack_coef, "verdicts": verdicts,
           "joint_rho_fav": gm.joint.rho_fav, "data_note": "lines from ESPN's scoreboard (one provider per game, near close)"}
    store.write_json(rep, "reports", "backtest_nba.json")
    print(json.dumps({"verdicts": verdicts, "kept": abl["kept"], "dropped": abl["dropped"]}, indent=1))
    return rep


def live_means(events: pd.DataFrame, lp) -> dict:
    """Model means for upcoming NBA games: append them as unplayed rows and
    rebuild features (point-in-time by construction)."""
    g = pd.read_parquet(store.history_path("nba_games"))
    fut = []
    for _, e in events.iterrows():
        ko = pd.Timestamp(e["commence_time"])
        fut.append({"game_id": e["game_key"], "season": int(g["season"].max()) if ko.month < 9 else ko.year,
                    "game_type": "REG", "kickoff": ko, "game_date": ko.tz_convert("America/New_York").strftime("%Y-%m-%d"),
                    "home_team": e["home_team"], "away_team": e["away_team"], "home_score": np.nan, "away_score": np.nan,
                    "neutral_site": int(bool(e.get("neutral", False))), "overtime": 0})
    tp = store.history_path("nba_team_games")
    frame = build_nba_features(pd.concat([g, pd.DataFrame(fut)], ignore_index=True), pd.read_parquet(tp) if tp.exists() else None)
    fr = frame[frame["game_id"].isin(set(events["game_key"]))]
    if fr.empty:
        return {}
    p = lp.model.predict_frame(fr)
    return {r["game_id"]: (float(r["pred_margin"]), float(r["pred_total"])) for _, r in p.iterrows()}


def key_players(teams: list[str]) -> list[tuple[str, str]]:
    """Top players per team by ESPN roster order is not usage-ranked, so for
    now the NBA news scan covers each team's injury-listed players (from the
    injury feed) plus team-level news; player usage ranks arrive with the
    NBA props model."""
    return []

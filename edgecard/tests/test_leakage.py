"""Leakage tests: no feature for a game may depend on that game's (or any
later game's) outcome.

Method: build features, then change the outcome of one game (scores and
the per-team box stats for that game) and rebuild. That game's own
features and every earlier game's features must be bit-for-bit identical;
the next game involving the same team must change (proves the test can
detect information flow at all).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data_pipeline.schedule_features import team_schedule_features
from models.nfl_features import all_feature_cols, build_nfl_features

TEAMS = ["KC", "BUF", "DEN", "LV", "NE", "MIA"]


def _synthetic(n_weeks: int = 8, seed: int = 0):
    rng = np.random.default_rng(seed)
    games, tg = [], []
    start = pd.Timestamp("2023-09-10")
    for w in range(n_weeks):
        order = rng.permutation(TEAMS)
        for i in range(0, len(order), 2):
            h, a = order[i], order[i + 1]
            hs, as_ = int(rng.integers(10, 35)), int(rng.integers(10, 35))
            gid = f"2023_{w + 1:02d}_{a}_{h}"
            games.append(dict(game_id=gid, season=2023, game_type="REG", week=w + 1,
                              gameday=(start + pd.Timedelta(days=7 * w)).date().isoformat(), gametime="13:00",
                              home_team=h, away_team=a, home_score=hs, away_score=as_, location="Home",
                              overtime=0, div_game=0, roof="outdoors", temp=60.0, wind=5.0,
                              home_qb_id=f"qb_{h}", away_qb_id=f"qb_{a}", home_coach=f"c_{h}", away_coach=f"c_{a}",
                              spread_line=0.0, total_line=44.0, home_moneyline=-110, away_moneyline=-110,
                              home_spread_odds=-110, away_spread_odds=-110, over_odds=-110, under_odds=-110))
            for team, opp, is_home in ((h, a, 1), (a, h, 0)):
                row = {"game_id": gid, "team": team, "opp": opp, "is_home": is_home, "season": 2023, "week": w + 1,
                       "home_team": h, "away_team": a}
                for c in ["plays", "epa_play", "success_rate", "pass_epa", "rush_epa", "pressure_rate_allowed",
                          "rz_td_rate", "st_epa", "proe", "fumble_luck", "sack_rate", "interceptions", "fumbles",
                          "fumbles_lost", "takeaways", "giveaways"]:
                    row[c] = float(rng.normal())
                    row[f"def_{c}"] = float(rng.normal())
                tg.append(row)
    return pd.DataFrame(games), pd.DataFrame(tg)


def _perturb(games: pd.DataFrame, tg: pd.DataFrame, gid: str):
    g2, t2 = games.copy(), tg.copy()
    i = g2.index[g2["game_id"] == gid][0]
    g2.loc[i, "home_score"] += 40
    g2.loc[i, "away_score"] = 0
    g2.loc[i, "overtime"] = 1
    num = t2.select_dtypes("number").columns.difference(["is_home", "season", "week"])
    t2.loc[t2["game_id"] == gid, num] = t2.loc[t2["game_id"] == gid, num] * 5 + 3
    return g2, t2


def test_nfl_features_do_not_see_own_or_future_results():
    games, tg = _synthetic()
    target = games.iloc[len(games) // 2]["game_id"]
    base = build_nfl_features(games, tg).set_index("game_id")
    g2, t2 = _perturb(games, tg, target)
    pert = build_nfl_features(g2, t2).set_index("game_id")
    cols = all_feature_cols()
    order = list(base.index)
    k = order.index(target)
    for gid in order[: k + 1]:
        a = base.loc[gid, cols].astype(float)
        b = pert.loc[gid, cols].astype(float)
        assert np.allclose(a.fillna(-999).values, b.fillna(-999).values), f"feature leak into {gid}"
    # sanity: some later game featuring the same teams must change
    teams = {base.loc[target, "home_team"], base.loc[target, "away_team"]}
    later = [g for g in order[k + 1:] if {base.loc[g, "home_team"], base.loc[g, "away_team"]} & teams]
    assert later, "synthetic schedule should have a later game for these teams"
    changed = any(not np.allclose(base.loc[g, cols].astype(float).fillna(-999).values,
                                  pert.loc[g, cols].astype(float).fillna(-999).values) for g in later)
    assert changed, "perturbation should propagate to later games (otherwise the test is vacuous)"


def test_targets_and_prices_are_not_feature_columns():
    cols = set(all_feature_cols())
    forbidden = {"margin", "total_pts", "home_score", "away_score", "spread_line", "total_line", "home_moneyline",
                 "away_moneyline", "over_odds", "under_odds", "home_spread_odds", "away_spread_odds", "overtime"}
    assert not (cols & forbidden)


def test_schedule_features_use_only_previous_overtime():
    games, _ = _synthetic()
    games["game_date"] = games["gameday"]
    target = games.iloc[5]["game_id"]
    a = team_schedule_features(games, "NFL").set_index(["game_id", "team"])
    g2 = games.copy()
    g2.loc[g2["game_id"] == target, "overtime"] = 1
    b = team_schedule_features(g2, "NFL").set_index(["game_id", "team"])
    pd.testing.assert_frame_equal(a.loc[[target]], b.loc[[target]])


@pytest.mark.parametrize("seed", [1, 2])
def test_elo_is_pre_game(seed):
    games, tg = _synthetic(seed=seed)
    f = build_nfl_features(games, tg)
    first = f.iloc[:3]
    assert (first["elo_home"] == 1500).all() and (first["elo_away"] == 1500).all()

"""Feature engineering: joins games + team_game_stats + injuries + Elo ratings
into a flat per-game feature frame for the GBM models.

Key design choice: every stat feature is computed as a *rolling, pre-game*
value (trailing N-game average as of the day before this game), never the
same game's own final stats — using this game's own final stats to predict
this game is leakage, full stop. `build_feature_frame` enforces this by
shifting each team's rolling stats by one game before joining.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from models.elo import DEFAULT_RATING

FOOTBALL_STAT_COLS = [
    "epa_per_play",
    "success_rate",
    "pass_epa_per_play",
    "rush_epa_per_play",
    "red_zone_pct",
    "third_down_pct",
    "pressure_rate",
    "pff_off_grade",
    "pff_def_grade",
]

BASKETBALL_STAT_COLS = [
    "off_rating",
    "def_rating",
    "pace",
    "efg_pct",
    "tov_pct",
    "orb_pct",
    "ftr",
    "net_rating_lineup_wtd",
]

CONTEXT_COLS = [
    "rest_days",
    "travel_mi",
    "is_dome",
    "weather_temp_f",
    "weather_wind_mph",
]


def _rolling_team_stats(team_game_stats: pd.DataFrame, stat_cols: list[str], window: int = 8) -> pd.DataFrame:
    """team_game_stats must be sorted by (team, game_date) ascending and carry
    a `game_date` column joined in by the caller. Returns rolling means
    SHIFTED by one so the value for game N never includes game N's own stats.
    """
    df = team_game_stats.sort_values(["team", "game_date"]).copy()
    for col in stat_cols:
        if col not in df.columns:
            continue
        df[f"{col}_roll"] = (
            df.groupby("team")[col]
            .apply(lambda s: s.shift(1).rolling(window, min_periods=2).mean())
            .reset_index(level=0, drop=True)
        )
    return df


def build_feature_frame(
    games: pd.DataFrame,
    team_game_stats: pd.DataFrame,
    sport: str,
    elo_ratings_by_date: dict[str, dict[str, float]] | None = None,
    rolling_window: int = 8,
) -> pd.DataFrame:
    """
    games: columns game_id, sport, season, game_date, home_team, away_team,
           home_score, away_score, home_rest_days, away_rest_days,
           home_travel_mi, away_travel_mi, is_dome, weather_temp_f,
           weather_wind_mph, neutral_site
    team_game_stats: columns game_id, team, is_home, <stat cols>
    elo_ratings_by_date: optional {game_id: {team: pre_game_elo}} precomputed
           walk-forward so there's no leakage (see models/backtest.py, which
           is the caller responsible for producing this without lookahead).

    Returns one row per game with home-minus-away differential features.
    """
    stat_cols = FOOTBALL_STAT_COLS if sport in ("NFL", "NCAAF") else BASKETBALL_STAT_COLS

    tgs = team_game_stats.merge(games[["game_id", "game_date"]], on="game_id", how="left")
    tgs = _rolling_team_stats(tgs, stat_cols, window=rolling_window)

    roll_cols = [f"{c}_roll" for c in stat_cols if f"{c}_roll" in tgs.columns]
    home_stats = tgs[tgs["is_home"] == 1][["game_id", "team"] + roll_cols].add_prefix("home_")
    home_stats = home_stats.rename(columns={"home_game_id": "game_id", "home_team": "home_team_chk"})
    away_stats = tgs[tgs["is_home"] == 0][["game_id", "team"] + roll_cols].add_prefix("away_")
    away_stats = away_stats.rename(columns={"away_game_id": "game_id", "away_team": "away_team_chk"})

    df = games.merge(home_stats, on="game_id", how="left").merge(away_stats, on="game_id", how="left")

    for c in roll_cols:
        df[f"diff_{c}"] = df[f"home_{c}"] - df[f"away_{c}"]

    df["rest_diff"] = df.get("home_rest_days", np.nan) - df.get("away_rest_days", np.nan)
    df["travel_diff"] = df.get("home_travel_mi", np.nan) - df.get("away_travel_mi", np.nan)
    df["is_dome"] = df.get("is_dome", 0)
    df["neutral_site"] = df.get("neutral_site", 0)

    if elo_ratings_by_date:
        df["home_elo_pre"] = df.apply(
            lambda r: elo_ratings_by_date.get(r["game_id"], {}).get(r["home_team"], np.nan), axis=1
        )
        df["away_elo_pre"] = df.apply(
            lambda r: elo_ratings_by_date.get(r["game_id"], {}).get(r["away_team"], np.nan), axis=1
        )
        df["elo_diff"] = df["home_elo_pre"] - df["away_elo_pre"]

    df["margin"] = df["home_score"] - df["away_score"]
    df["total"] = df["home_score"] + df["away_score"]
    df["home_win"] = (df["margin"] > 0).astype("Int64")

    return df


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Selects the engineered (diff_/rest_/travel_/elo_) columns, dropping
    identifiers and targets, for direct use as model X."""
    exclude_prefixes = ("home_score", "away_score", "margin", "total", "home_win")
    exclude_exact = {
        "game_id",
        "sport",
        "season",
        "week",
        "game_date",
        "home_team",
        "away_team",
        "is_final",
        "referee_crew",
        "weather_precip",
        "home_team_chk",
        "away_team_chk",
    }
    cols = []
    for c in df.columns:
        if c in exclude_exact or c.startswith(exclude_prefixes):
            continue
        if df[c].dtype.kind in "biuf":  # bool/int/uint/float only
            cols.append(c)
    return cols


def select_populated_feature_columns(df: pd.DataFrame, cols: list[str], min_frac: float = 0.5) -> list[str]:
    """Drops feature columns that are missing more than `1 - min_frac` of the
    time (e.g. PFF grades in a data source that doesn't supply them).
    Training on a column that's entirely NaN would either crash a dropna-based
    filter (every row gets dropped) or feed XGBoost a column with zero signal
    — better to drop it up front and say so, which is what callers should log
    (the dropped-vs-kept set is the return value's complement in `cols`).
    """
    return [c for c in cols if df[c].notna().mean() > min_frac]


def build_live_feature_rows(
    games_hist: pd.DataFrame,
    stats_hist: pd.DataFrame,
    games_today: pd.DataFrame,
    sport: str,
    elo_ratings: dict[str, float],
    rolling_window: int = 8,
) -> pd.DataFrame:
    """Projects today's (unplayed) games into the SAME engineered-feature
    space used at training time, with zero leakage from the game itself.

    The trick: append one placeholder team_game_stats row per team for each
    of today's games. `_rolling_team_stats` computes every rolling stat with
    `shift(1)` before averaging, so a row's OWN stat values are never read
    when computing that row's rolling feature — only the real, already-
    completed games strictly before it are. That means the placeholder row's
    values are irrelevant filler (NaN is fine); what actually lands in
    today's feature row is each team's trailing rolling average over their
    real last `rolling_window` completed games, exactly as if this were a
    held-out game in a backtest fold. This keeps live prediction and
    training feature engineering running through the identical code path
    (build_feature_frame), which is what prevents train/serve skew.

    `elo_ratings`: each team's CURRENT Elo rating (i.e. after their most
    recent completed game) — see models/production.py for how this is
    computed alongside the historical, walk-forward per-game ratings used
    at training time.
    """
    stat_cols = FOOTBALL_STAT_COLS if sport in ("NFL", "NCAAF") else BASKETBALL_STAT_COLS

    combined_games = pd.concat([games_hist, games_today], ignore_index=True, sort=False)
    # games_today's numeric fields are frequently None (rest days unknown,
    # travel/weather not sourced live yet — see scripts/daily_report.py). A
    # column that's all-None in one half of a concat comes back dtype
    # 'object' even when the other half is float64, which XGBoost rejects
    # outright at predict time. Coercing to numeric fixes the dtype AND
    # turns None into a proper NaN (which XGBoost natively handles as
    # missing, same as it saw during training on real missing weather/dome
    # games).
    numeric_game_cols = [
        "home_score", "away_score", "home_rest_days", "away_rest_days",
        "home_travel_mi", "away_travel_mi", "weather_temp_f", "weather_wind_mph",
    ]
    for c in numeric_game_cols:
        if c in combined_games.columns:
            combined_games[c] = pd.to_numeric(combined_games[c], errors="coerce")

    placeholder_rows = []
    for _, g in games_today.iterrows():
        for team, is_home in ((g["home_team"], 1), (g["away_team"], 0)):
            row = {"game_id": g["game_id"], "team": team, "is_home": is_home}
            row.update({c: np.nan for c in stat_cols})
            placeholder_rows.append(row)
    combined_stats = pd.concat([stats_hist, pd.DataFrame(placeholder_rows)], ignore_index=True, sort=False)
    for c in stat_cols:
        if c in combined_stats.columns:
            combined_stats[c] = pd.to_numeric(combined_stats[c], errors="coerce")

    elo_by_game = {
        g["game_id"]: {
            g["home_team"]: elo_ratings.get(g["home_team"], DEFAULT_RATING),
            g["away_team"]: elo_ratings.get(g["away_team"], DEFAULT_RATING),
        }
        for _, g in games_today.iterrows()
    }

    feat_df = build_feature_frame(
        combined_games, combined_stats, sport, elo_ratings_by_date=elo_by_game, rolling_window=rolling_window
    )
    today_ids = set(games_today["game_id"])
    return feat_df[feat_df["game_id"].isin(today_ids)].reset_index(drop=True)

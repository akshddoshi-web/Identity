"""Schedule / travel / fatigue features, computed per team per game from the
schedule alone.

Everything here only reads games *before* the one being described (a team's
previous game location and date), plus the current game's own venue and
date — both of which are known when the schedule is published. No results
of the current game are ever read, so these are leak-free by construction
(tests/test_leakage.py checks that). One exception is explicitly named:
`prev_overtime` uses the PREVIOUS game's overtime flag, which is known once
that game ends, never the current game's.

Output: one row per (game_id, team) with
  rest_days, is_b2b, is_3in4, games_last_7d, short_week (NFL: <=4 days),
  travel_mi (from previous game venue), tz_shift (hours, signed, east > 0),
  venue_altitude_ft, road_trip_len (consecutive away games incl. this one),
  prev_overtime.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data_pipeline.venues import haversine_miles, utc_offset_hours, venues


def _venue_team(row: pd.Series) -> str:
    return row["home_team"]


def team_schedule_features(games: pd.DataFrame, league: str) -> pd.DataFrame:
    """games: game_id, game_date (ISO date or datetime), home_team, away_team,
    optional neutral_site, optional overtime (0/1, NaN if unplayed)."""
    vmap = venues(league)
    g = games.copy()
    g["_date"] = pd.to_datetime(g["game_date"].astype(str).str[:10])
    if "overtime" not in g.columns:
        g["overtime"] = np.nan

    long_rows = []
    for _, r in g.iterrows():
        venue_team = _venue_team(r)
        for team, is_home in ((r["home_team"], 1), (r["away_team"], 0)):
            long_rows.append(
                {
                    "game_id": r["game_id"],
                    "team": team,
                    "is_home": is_home,
                    "_date": r["_date"],
                    "venue_team": venue_team,
                    "overtime": r["overtime"],
                }
            )
    long = pd.DataFrame(long_rows).sort_values(["team", "_date", "game_id"]).reset_index(drop=True)

    out = []
    for team, tg in long.groupby("team", sort=False):
        tg = tg.reset_index(drop=True)
        dates = tg["_date"].tolist()
        prev_venue = None
        road_len = 0
        for i, row in tg.iterrows():
            d = dates[i]
            venue = vmap.get(row["venue_team"])
            rest = (d - dates[i - 1]).days if i > 0 else np.nan
            games_last_4 = sum(1 for x in dates[max(0, i - 3): i + 1] if (d - x).days <= 3)
            games_last_7 = sum(1 for x in dates[max(0, i - 6): i] if (d - x).days <= 7)
            if venue is not None and prev_venue is not None:
                travel = haversine_miles((prev_venue.lat, prev_venue.lon), (venue.lat, venue.lon))
                tz_shift = utc_offset_hours(venue.tz, d.to_pydatetime()) - utc_offset_hours(prev_venue.tz, d.to_pydatetime())
            else:
                travel, tz_shift = np.nan, np.nan
            road_len = road_len + 1 if row["is_home"] == 0 else 0
            out.append(
                {
                    "game_id": row["game_id"],
                    "team": team,
                    "rest_days": rest,
                    "is_b2b": float(rest == 1) if not np.isnan(rest) else np.nan,
                    "is_3in4": float(games_last_4 >= 3),
                    "games_last_7d": float(games_last_7),
                    "short_week": float(rest <= 4) if (league == "NFL" and not np.isnan(rest)) else (0.0 if league == "NFL" else np.nan),
                    "travel_mi": travel,
                    "tz_shift": tz_shift,
                    "venue_altitude_ft": venue.altitude_ft if venue else np.nan,
                    "road_trip_len": float(road_len),
                    "prev_overtime": float(tg["overtime"].iloc[i - 1]) if i > 0 and pd.notna(tg["overtime"].iloc[i - 1]) else 0.0,
                }
            )
            prev_venue = venue if venue is not None else prev_venue
    return pd.DataFrame(out)


def game_level_schedule_features(games: pd.DataFrame, league: str) -> pd.DataFrame:
    """Pivots team rows to one row per game with home_/away_ columns and
    home-minus-away differentials for the model."""
    t = team_schedule_features(games, league)
    home = games[["game_id", "home_team"]].merge(t, left_on=["game_id", "home_team"], right_on=["game_id", "team"])
    away = games[["game_id", "away_team"]].merge(t, left_on=["game_id", "away_team"], right_on=["game_id", "team"])
    cols = [c for c in t.columns if c not in ("game_id", "team")]
    home = home[["game_id"] + cols].add_prefix("h_").rename(columns={"h_game_id": "game_id"})
    away = away[["game_id"] + cols].add_prefix("a_").rename(columns={"a_game_id": "game_id"})
    df = home.merge(away, on="game_id")
    df["sched_rest_diff"] = df["h_rest_days"] - df["a_rest_days"]
    df["sched_travel_diff"] = df["h_travel_mi"].fillna(0) - df["a_travel_mi"].fillna(0)
    df["sched_b2b_diff"] = df["h_is_b2b"].fillna(0) - df["a_is_b2b"].fillna(0)
    df["sched_3in4_diff"] = df["h_is_3in4"] - df["a_is_3in4"]
    df["sched_tz_away_abs"] = df["a_tz_shift"].abs()
    df["sched_short_week_diff"] = df["h_short_week"].fillna(0) - df["a_short_week"].fillna(0)
    df["sched_prev_ot_diff"] = df["h_prev_overtime"] - df["a_prev_overtime"]
    df["sched_altitude_ft"] = df["h_venue_altitude_ft"]
    df["sched_road_trip_away"] = df["a_road_trip_len"]
    return df

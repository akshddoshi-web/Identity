"""Real NFL data from nflverse-data (the data warehouse behind nflfastR/
nfl_data_py). Play-by-play parquet files are published as public GitHub
release assets — no API key needed:

    https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{year}.parquet

Each row is one play and already carries `epa`, `success`, down/distance,
play_type, and (since ~2013) the game's closing `spread_line` and
`total_line` — nflverse's own historical betting-line compilation. There is
no moneyline in this file; live moneyline comes from data_pipeline/ingest_odds.py
once you have a real ODDS_API_KEY.

IMPORTANT sign convention: nflverse's `spread_line` is the home team's
*expected margin* (positive = home favored), which is the OPPOSITE sign of
this repo's own OddsSnapshot.home_point convention (negative = home favored,
matching how a sportsbook actually displays it — see
generate_sample_data.py and edge/edge_detection.py). This was verified
empirically against real blowout games before writing this module — see the
`spread_line` -> `home_point` negation below. Getting this backwards would
silently invert every spread edge/cover-probability calculation.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import requests

from data_pipeline.ingest_games import compute_rest_days, haversine_miles
from data_pipeline.ingest_advanced_stats import EPACalculator
from data_pipeline.schema import GameRecord, OddsSnapshot, TeamGameStats

PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{year}.parquet"

# Approximate stadium-city coordinates (lat, lon), by the team abbreviation
# nflverse uses for that franchise AT THE TIME (historical relocations keep
# their old abbreviation in old seasons' data — e.g. STL/SD/OAK before their
# moves — so travel distance stays accurate for the season it describes,
# though it does mean a relocated franchise's rolling form resets under its
# new abbreviation, same as a new team would).
TEAM_COORDS: dict[str, tuple[float, float]] = {
    "ARI": (33.5276, -112.2626), "ATL": (33.7554, -84.4008), "BAL": (39.2780, -76.6227),
    "BUF": (42.7738, -78.7870), "CAR": (35.2258, -80.8528), "CHI": (41.8623, -87.6167),
    "CIN": (39.0955, -84.5160), "CLE": (41.5061, -81.6995), "DAL": (32.7473, -97.0945),
    "DEN": (39.7439, -105.0201), "DET": (42.3400, -83.0456), "GB": (44.5013, -88.0622),
    "HOU": (29.6847, -95.4107), "IND": (39.7601, -86.1639), "JAX": (30.3239, -81.6373),
    "KC": (39.0489, -94.4839), "LA": (33.9535, -118.3392), "LAC": (33.9535, -118.3392),
    "LV": (36.0909, -115.1833), "MIA": (25.9580, -80.2389), "MIN": (44.9736, -93.2575),
    "NE": (42.0909, -71.2643), "NO": (29.9509, -90.0815), "NYG": (40.8135, -74.0745),
    "NYJ": (40.8135, -74.0745), "OAK": (37.7516, -122.2005), "PHI": (39.9008, -75.1675),
    "PIT": (40.4468, -80.0158), "SD": (32.7831, -117.1196), "SEA": (47.5952, -122.3316),
    "SF": (37.7133, -122.3861), "STL": (38.6328, -90.1885), "TB": (27.9759, -82.5033),
    "TEN": (36.1665, -86.7713), "WAS": (38.9077, -76.8645),
}


def fetch_pbp_years(years: list[int]) -> pd.DataFrame:
    frames = []
    for year in years:
        url = PBP_URL.format(year=year)
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        df = pd.read_parquet(io.BytesIO(resp.content), engine="pyarrow")
        frames.append(df)
        print(f"  NFL {year}: {len(df):,} plays")
    return pd.concat(frames, ignore_index=True)


def _build_games(pbp: pd.DataFrame) -> list[GameRecord]:
    g = pbp.groupby("game_id", as_index=False).first()
    records = []
    for _, row in g.iterrows():
        is_dome = bool(row.get("roof") in ("dome", "closed"))
        neutral = bool(row.get("location") == "Neutral")
        home_coord = TEAM_COORDS.get(row["home_team"])
        away_coord = TEAM_COORDS.get(row["away_team"])
        away_travel = haversine_miles(away_coord, home_coord)  # away team travels to the home city
        records.append(
            GameRecord(
                game_id=row["game_id"],
                sport="NFL",
                season=int(row["season"]) if "season" in row and pd.notna(row.get("season")) else int(str(row["game_id"])[:4]),
                week=int(row["week"]) if pd.notna(row.get("week")) else None,
                game_date=str(row["game_date"]),
                home_team=row["home_team"],
                away_team=row["away_team"],
                home_score=int(row["home_score"]) if pd.notna(row.get("home_score")) else None,
                away_score=int(row["away_score"]) if pd.notna(row.get("away_score")) else None,
                is_final=pd.notna(row.get("home_score")),
                neutral_site=neutral,
                home_travel_mi=0.0,
                away_travel_mi=away_travel,
                weather_temp_f=float(row["temp"]) if pd.notna(row.get("temp")) else None,
                weather_wind_mph=float(row["wind"]) if pd.notna(row.get("wind")) else None,
                is_dome=is_dome,
            )
        )
    compute_rest_days(records)
    return records


def _build_odds(pbp: pd.DataFrame) -> list[OddsSnapshot]:
    """Real closing spread/total lines from nflverse's own compilation.
    No book-specific vig is available here, so both sides are priced at the
    standard -110/-110 — the LINE VALUES are real, only the assumed vig is
    a standard-market approximation. No moneyline: not present in this
    source (see module docstring)."""
    g = pbp.groupby("game_id", as_index=False).first()
    snaps: list[OddsSnapshot] = []
    for _, row in g.iterrows():
        captured_at = str(row["game_date"])
        if pd.notna(row.get("spread_line")):
            home_point = -float(row["spread_line"])  # sign flip — see module docstring
            snaps.append(
                OddsSnapshot(
                    game_id=row["game_id"], book="nflverse_consensus", snapshot_type="close",
                    captured_at=captured_at, market="spread", home_price=-110, away_price=-110,
                    home_point=home_point, away_point=-home_point,
                )
            )
        if pd.notna(row.get("total_line")):
            total = float(row["total_line"])
            snaps.append(
                OddsSnapshot(
                    game_id=row["game_id"], book="nflverse_consensus", snapshot_type="close",
                    captured_at=captured_at, market="total", home_price=-110, away_price=-110,
                    home_point=total, away_point=total,
                )
            )
    return snaps


def _build_team_game_stats(pbp: pd.DataFrame) -> list[TeamGameStats]:
    plays = pbp.copy()
    plays["pressure"] = (plays.get("qb_hit") == 1) | (plays.get("sack") == 1)
    # EPACalculator expects real plays only (pass/run with a defined down);
    # special teams/no-plays naturally fall out of its own filtering.
    return EPACalculator().compute(plays)


def build_nfl_dataset(years: list[int]) -> tuple[list[GameRecord], list[TeamGameStats], list[OddsSnapshot]]:
    pbp = fetch_pbp_years(years)
    games = _build_games(pbp)
    valid_ids = {g.game_id for g in games}
    stats = [s for s in _build_team_game_stats(pbp) if s.game_id in valid_ids]
    odds = [o for o in _build_odds(pbp) if o.game_id in valid_ids]
    return games, stats, odds

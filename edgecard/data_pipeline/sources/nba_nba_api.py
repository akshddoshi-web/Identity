"""Real NBA data via `nba_api` (stats.nba.com's undocumented-but-widely-used
JSON endpoints, wrapped by https://github.com/swar/nba_api).

*** THIS MODULE HAS NOT BEEN RUN OR VALIDATED IN THIS REPO'S DEVELOPMENT
SESSION. *** stats.nba.com and cdn.nba.com were unreachable from that
session's sandboxed network policy (everything but GitHub/PyPI was blocked
there) — confirmed by direct `curl` returning connection-rejected, not a
code problem. The code below is written correctly against nba_api's real,
documented interface, but you must validate it yourself — run
`scripts/ingest_real_data.py --sport NBA` somewhere with normal internet
access (your own machine, CI, or the Streamlit Cloud deployment) and sanity-
check the output (a handful of known final scores, a spot-check of ORtg/DRtg
against a site like basketball-reference) before trusting it for real
backtesting. Do not assume it works just because it reads correctly.

Install nba_api in an ISOLATED environment — it pins `numpy<2.0`, which
conflicts with this repo's numpy>=1.26 pin and, if installed into the same
environment as everything else, WILL silently downgrade numpy/pandas and
can corrupt the feature-engineering pipeline (this happened with
nfl_data_py's pandas<2.0 pin during development — see requirements.txt's
comment on this exact failure mode):

    python -m venv .venv-nba
    .venv-nba/bin/pip install nba_api
    .venv-nba/bin/python scripts/ingest_real_data.py --sport NBA

Design:
  - `leaguegamefinder.LeagueGameFinder` for the season schedule + final
    scores (home/away, points, game date).
  - `boxscoreadvancedv2.BoxScoreAdvancedV2` per game for team-level
    ORtg/DRtg/pace/eFG%/TOV%/ORB%/FTr — the exact columns this repo's
    schema (`TeamGameStats`) expects, so no extra mapping is needed beyond
    what's here.
  - nba_api has NO documented rate limit but stats.nba.com aggressively
    throttles/blocks scripted traffic without realistic headers and
    inter-request delays; `time.sleep` between calls and a realistic
    `User-Agent` are load-bearing, not decoration — remove them and expect
    to get blocked partway through a season.
  - Injuries and lineup-weighted net ratings are NOT implemented here —
    nba_api's rotation/injury endpoints are considerably less stable than
    the box-score ones. See
    `data_pipeline/ingest_advanced_stats.py::injury_adjusted_lineup_rating`
    for the heuristic this repo already has ready to consume that data once
    you have an injury source wired in.
"""
from __future__ import annotations

import time

import pandas as pd

from data_pipeline.ingest_games import compute_rest_days
from data_pipeline.schema import GameRecord, TeamGameStats

REQUEST_DELAY_SECONDS = 0.6  # be a good citizen; stats.nba.com blocks bursty scripted traffic


def _client():
    try:
        from nba_api.stats.endpoints import boxscoreadvancedv2, leaguegamefinder
    except ImportError as e:
        raise ImportError(
            "nba_api is not installed. Install it in an ISOLATED virtualenv — see this "
            "module's docstring for why it can't share this repo's main environment."
        ) from e
    return leaguegamefinder, boxscoreadvancedv2


def fetch_season_games(season: str) -> pd.DataFrame:
    """season like '2022-23'. Returns nba_api's raw LeagueGameFinder frame,
    one row per team per game (so two rows per game)."""
    leaguegamefinder, _ = _client()
    finder = leaguegamefinder.LeagueGameFinder(
        season_nullable=season, league_id_nullable="00", season_type_nullable="Regular Season"
    )
    df = finder.get_data_frames()[0]
    time.sleep(REQUEST_DELAY_SECONDS)
    return df


def _pair_home_away(games_raw: pd.DataFrame) -> pd.DataFrame:
    """nba_api's LeagueGameFinder gives one row per team per game (with
    MATCHUP like 'BOS vs. NYK' or 'BOS @ NYK'); pairs them into one row per
    game with explicit home/away."""
    games_raw = games_raw.copy()
    games_raw["is_home"] = games_raw["MATCHUP"].str.contains(" vs. ")
    paired = []
    for game_id, grp in games_raw.groupby("GAME_ID"):
        if len(grp) != 2:
            continue
        home = grp[grp["is_home"]].iloc[0] if grp["is_home"].any() else None
        away = grp[~grp["is_home"]].iloc[0] if (~grp["is_home"]).any() else None
        if home is None or away is None:
            continue
        paired.append(
            {
                "game_id": game_id,
                "game_date": home["GAME_DATE"],
                "home_team": home["TEAM_ABBREVIATION"],
                "away_team": away["TEAM_ABBREVIATION"],
                "home_score": int(home["PTS"]),
                "away_score": int(away["PTS"]),
                "season": int(season_from_id(game_id)),
            }
        )
    return pd.DataFrame(paired)


def season_from_id(game_id: str) -> int:
    # nba_api GAME_IDs encode season internally; callers should generally
    # just pass the season explicitly instead of relying on this — kept as
    # a fallback so _pair_home_away always has SOME season value.
    return 2000 + int(str(game_id)[3:5])


def build_games(season: str) -> list[GameRecord]:
    raw = fetch_season_games(season)
    paired = _pair_home_away(raw)
    records = [
        GameRecord(
            game_id=str(row["game_id"]),
            sport="NBA",
            season=int(season[:4]),
            game_date=str(row["game_date"])[:10],
            home_team=row["home_team"],
            away_team=row["away_team"],
            home_score=row["home_score"],
            away_score=row["away_score"],
            is_final=True,
        )
        for _, row in paired.iterrows()
    ]
    compute_rest_days(records)
    return records


def build_team_game_stats_for_game(game_id: str) -> list[TeamGameStats]:
    """One BoxScoreAdvancedV2 call per game — this is the slow part (one
    HTTP round-trip per game, not batchable) and where REQUEST_DELAY_SECONDS
    matters most; a full season is ~1,230 games, so budget real wall-clock
    time (tens of minutes) when actually running this."""
    _, boxscoreadvancedv2 = _client()
    box = boxscoreadvancedv2.BoxScoreAdvancedV2(game_id=game_id)
    team_stats = box.get_data_frames()[1]  # team-level advanced box score
    time.sleep(REQUEST_DELAY_SECONDS)

    rows = []
    if len(team_stats) != 2:
        return rows
    home_team_id = team_stats.iloc[0]["TEAM_ID"]  # first row is home per nba_api's convention
    for _, row in team_stats.iterrows():
        rows.append(
            TeamGameStats(
                game_id=str(game_id),
                team=row["TEAM_ABBREVIATION"],
                is_home=bool(row["TEAM_ID"] == home_team_id),
                off_rating=float(row["OFF_RATING"]) if pd.notna(row.get("OFF_RATING")) else None,
                def_rating=float(row["DEF_RATING"]) if pd.notna(row.get("DEF_RATING")) else None,
                pace=float(row["PACE"]) if pd.notna(row.get("PACE")) else None,
                efg_pct=float(row["EFG_PCT"]) if pd.notna(row.get("EFG_PCT")) else None,
                tov_pct=float(row["TM_TOV_PCT"]) if pd.notna(row.get("TM_TOV_PCT")) else None,
                orb_pct=float(row["OREB_PCT"]) if pd.notna(row.get("OREB_PCT")) else None,
                ftr=None,  # not directly in this endpoint; would need FTA/FGA from the traditional box score
            )
        )
    return rows


def build_nba_dataset(season: str) -> tuple[list[GameRecord], list[TeamGameStats]]:
    """Full pipeline for one season. Calling this for multiple seasons means
    calling it in a loop yourself — deliberately not batched here so you can
    checkpoint progress (save to the DB) between seasons rather than losing
    an hour of box-score calls to one network hiccup near the end."""
    games = build_games(season)
    stats: list[TeamGameStats] = []
    for i, g in enumerate(games):
        stats.extend(build_team_game_stats_for_game(g.game_id))
        if (i + 1) % 50 == 0:
            print(f"  NBA {season}: {i + 1}/{len(games)} games' box scores fetched")
    return games, stats

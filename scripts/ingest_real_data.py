"""Ingests REAL historical data — replacing scripts/generate_sample_data.py's
synthetic data — from public, no-API-key-required sources:

  NFL:   nflverse-data play-by-play (GitHub release assets)
  NCAAF: cfbfastR-data (schedules, play-by-play, and REAL historical betting
         lines, all bundled in the sportsdataverse/cfbfastr-data repo)
  NBA:   not run by this script — see data_pipeline/sources/nba_nba_api.py's
         module docstring for why, and README.md's "Data source availability"
         section for the honest status.

Run as: python scripts/ingest_real_data.py [--sport NFL|NCAAF] [--nfl-years ...] [--ncaaf-years ...]

Wipes and rebuilds the sports it's asked to touch (idempotent — re-run any
time to pull a fresh window of seasons). Leaves other sports' data alone.
"""
from __future__ import annotations

import argparse

from data_pipeline.db import connect, init_db
from data_pipeline.ingest_games import upsert_games
from data_pipeline.ingest_advanced_stats import upsert_team_game_stats
from data_pipeline.ingest_odds import store_odds_snapshots

DEFAULT_NFL_YEARS = list(range(2015, 2024))    # 9 seasons
DEFAULT_NCAAF_YEARS = list(range(2012, 2022))   # 10 seasons — matches cfbfastR-data's pbp coverage window


def _wipe_sport(conn, sport: str) -> None:
    """Deletes everything for one sport in FK-safe order, including any
    predictions/CLV/ledger rows logged against its (synthetic, in a fresh
    checkout) games — replacing a sport's data means replacing its whole
    history, not leaving orphaned bets pointing at games that no longer
    exist."""
    conn.execute(
        """DELETE FROM bet_ledger WHERE prediction_id IN (
               SELECT prediction_id FROM predictions WHERE sport = ?)""",
        (sport,),
    )
    conn.execute(
        """DELETE FROM clv_records WHERE prediction_id IN (
               SELECT prediction_id FROM predictions WHERE sport = ?)""",
        (sport,),
    )
    conn.execute("DELETE FROM predictions WHERE sport = ?", (sport,))
    conn.execute(
        "DELETE FROM odds_snapshots WHERE game_id IN (SELECT game_id FROM games WHERE sport = ?)", (sport,)
    )
    conn.execute(
        "DELETE FROM team_game_stats WHERE game_id IN (SELECT game_id FROM games WHERE sport = ?)", (sport,)
    )
    conn.execute("DELETE FROM games WHERE sport = ?", (sport,))


def ingest_nfl(conn, years: list[int]) -> None:
    from data_pipeline.sources.nfl_nflverse import build_nfl_dataset

    print(f"Fetching real NFL data for seasons {years[0]}-{years[-1]} from nflverse-data...")
    games, stats, odds = build_nfl_dataset(years)
    _wipe_sport(conn, "NFL")
    upsert_games(games, conn)
    upsert_team_game_stats(stats, conn)
    store_odds_snapshots(odds, conn)
    print(f"NFL: {len(games)} games, {len(stats)} team-game-stat rows, {len(odds)} real closing-line odds rows")


def ingest_ncaaf(conn, years: list[int], repo_path: str) -> None:
    from data_pipeline.sources.ncaaf_cfbfastr import build_ncaaf_dataset

    print(f"Parsing real NCAAF data for seasons {years[0]}-{years[-1]} from {repo_path}...")
    games, stats, odds = build_ncaaf_dataset(years, repo_path)
    _wipe_sport(conn, "NCAAF")
    upsert_games(games, conn)
    upsert_team_game_stats(stats, conn)
    store_odds_snapshots(odds, conn)
    print(f"NCAAF: {len(games)} games, {len(stats)} team-game-stat rows, {len(odds)} real odds rows")


def ingest_nba(conn, seasons: list[str]) -> None:
    """NOT exercised in this repo's own development session — nba_api needs
    stats.nba.com, which that sandboxed session's network policy blocked
    outright. The code is real and documented in
    data_pipeline/sources/nba_nba_api.py, but install nba_api in an isolated
    virtualenv (see that module's docstring) and validate the output
    yourself before trusting it."""
    from data_pipeline.sources.nba_nba_api import build_nba_dataset

    _wipe_sport(conn, "NBA")
    for season in seasons:
        print(f"Fetching real NBA data for {season} season via nba_api (slow: one HTTP call per game)...")
        games, stats = build_nba_dataset(season)
        upsert_games(games, conn)
        upsert_team_game_stats(stats, conn)
        print(f"NBA {season}: {len(games)} games, {len(stats)} team-game-stat rows (no historical odds — see README)")


def main():
    parser = argparse.ArgumentParser(description="Ingest real historical data (NFL, NCAAF, NBA).")
    parser.add_argument("--sport", choices=["NFL", "NCAAF", "NBA", "ALL"], default="ALL")
    parser.add_argument(
        "--nba-seasons", nargs="+", default=["2021-22", "2022-23", "2023-24"],
        help="NBA season strings like '2023-24'. Requires nba_api installed in an isolated venv — see data_pipeline/sources/nba_nba_api.py.",
    )
    parser.add_argument("--nfl-years", type=int, nargs="+", default=DEFAULT_NFL_YEARS)
    parser.add_argument("--ncaaf-years", type=int, nargs="+", default=DEFAULT_NCAAF_YEARS)
    parser.add_argument(
        "--cfbfastr-repo", default="/home/user/sportsdataverse/cfbfastr-data",
        help="Local path to a checkout of github.com/sportsdataverse/cfbfastr-data (see README for how to clone it).",
    )
    args = parser.parse_args()

    init_db()
    with connect() as conn:
        if args.sport in ("NFL", "ALL"):
            ingest_nfl(conn, args.nfl_years)
        if args.sport in ("NCAAF", "ALL"):
            ingest_ncaaf(conn, args.ncaaf_years, args.cfbfastr_repo)
        if args.sport == "NBA":
            # deliberately NOT part of "ALL" — needs nba_api in an isolated
            # venv (see ingest_nba's docstring), so it must be requested
            # explicitly rather than silently attempted (and failing) as
            # part of a routine NFL+NCAAF refresh.
            ingest_nba(conn, args.nba_seasons)

    if args.sport == "ALL":
        print(
            "\nDone with NFL + NCAAF. NBA was NOT touched — run with --sport NBA "
            "(after installing nba_api in an isolated venv) to populate it. "
            "See README's Data source availability section."
        )
    else:
        print(f"\nDone with {args.sport}.")


if __name__ == "__main__":
    main()

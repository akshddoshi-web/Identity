"""Real NCAAF data from sportsdataverse/cfbfastr-data — the data warehouse
behind the (R-only) cfbfastR package, and cfbfastR's own consensus-line
compilation. This repo is public (~7GB full history); clone it once and
point this module at the checkout:

    GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 \\
        https://github.com/sportsdataverse/cfbfastr-data /path/to/cfbfastr-data

The collegefootballdata.com API (what the `cfbd` Python package and the R
`cfbfastR` package call live) needs a free API key and, in this sandboxed
session, is also blocked by network policy — so this module reads the
already-computed CSV/parquet files cfbfastR's own CI publishes to that repo
instead of calling any live API.

Data used:
  - schedules/csv/cfb_schedules_{year}.csv: real final scores, attendance,
    venue, neutral-site flag. Reliable, present every season.
  - pbp/parquet/play_by_play_{year}.parquet: real play-by-play with EPA and
    a success flag, for team-game advanced stats. In this repo's current
    snapshot this only goes back to 2002 and only up to 2021 — seasons
    outside that window get schedule/game rows but no advanced stats, so
    they're unusable for model training (the pipeline drops them via its
    existing mostly-null feature filtering) even though this ingester still
    records the games themselves.
  - The SAME pbp file also carries the game's real closing spread
    (`homeTeamSpread`) and total (`overUnder`) — this repo also ships a
    separate book-level betting/csv/cfb_line_odds.csv.gz file with more
    detail (multiple books, moneyline), but its `abbr` column uses betting-
    provider short codes (e.g. "ASU", "KNT") that don't line up with the
    schedule file's full team names without a manual code->team mapping this
    module doesn't attempt — using the embedded per-play spread/total avoids
    that unreliable join. Net effect: like NFL, NCAAF gets real spread/total
    closing lines here but no historical moneyline (same standard -110/-110
    vig assumption; no book-specific juice available). Sign convention:
    `homeTeamSpread` is "home team's expected margin" (positive = home
    favored) — the SAME orientation as nflverse's `spread_line`, and the
    OPPOSITE of this repo's home_point convention — verified against real
    blowout games before writing this, same as the NFL module.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from data_pipeline.ingest_games import compute_rest_days
from data_pipeline.schema import GameRecord, OddsSnapshot, TeamGameStats

PASS_PLAY_TYPES = {
    "Pass Reception", "Pass Incompletion", "Passing Touchdown",
    "Pass Interception Return", "Interception", "Sack",
}
RUSH_PLAY_TYPES = {"Rush", "Rushing Touchdown"}


def _read_schedules(repo: Path, years: list[int]) -> pd.DataFrame:
    frames = []
    for year in years:
        path = repo / "schedules" / "csv" / f"cfb_schedules_{year}.csv"
        if not path.exists():
            print(f"  NCAAF {year}: no schedules file at {path}, skipping")
            continue
        df = pd.read_csv(path, low_memory=False)
        frames.append(df)
        print(f"  NCAAF {year}: {len(df)} scheduled games")
    if not frames:
        raise FileNotFoundError(f"No NCAAF schedule files found under {repo}/schedules/csv for years {years}")
    return pd.concat(frames, ignore_index=True)


def _read_pbp(repo: Path, years: list[int]) -> pd.DataFrame:
    frames = []
    for year in years:
        path = repo / "pbp" / "parquet" / f"play_by_play_{year}.parquet"
        if not path.exists():
            print(f"  NCAAF {year}: no pbp file at {path} (advanced stats/odds unavailable for this season)")
            continue
        df = pd.read_parquet(path, engine="pyarrow")
        frames.append(df)
        print(f"  NCAAF {year}: {len(df):,} plays")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _build_games(schedules: pd.DataFrame) -> list[GameRecord]:
    """FBS-vs-FBS games only. cfbfastR-data's schedules span every NCAA
    division (2021 alone has 2,408 rows), but FCS/D2/D3 games have no real
    betting market and would just dilute the FBS-level model with a very
    different quality of competition — "NCAAF" in a betting context means
    FBS."""
    records = []
    for _, row in schedules.iterrows():
        if not bool(row.get("completed", False)):
            continue
        if row.get("home_division") != "fbs" or row.get("away_division") != "fbs":
            continue
        records.append(
            GameRecord(
                game_id=str(int(row["game_id"])),
                sport="NCAAF",
                season=int(row["season"]),
                week=int(row["week"]) if pd.notna(row.get("week")) else None,
                game_date=str(row["start_date"])[:10],
                home_team=row["home_team"],
                away_team=row["away_team"],
                home_score=int(row["home_points"]) if pd.notna(row.get("home_points")) else None,
                away_score=int(row["away_points"]) if pd.notna(row.get("away_points")) else None,
                is_final=True,
                neutral_site=bool(row.get("neutral_site", False)),
            )
        )
    compute_rest_days(records)
    return records


def _build_odds(pbp: pd.DataFrame) -> list[OddsSnapshot]:
    if pbp.empty:
        return []
    g = pbp.groupby("game_id", as_index=False).first()
    snaps: list[OddsSnapshot] = []
    for _, row in g.iterrows():
        game_id = str(int(row["game_id"]))
        captured_at = f"{int(row['season'])}-01-01"  # exact date not carried per-play; season-level placeholder
        if pd.notna(row.get("homeTeamSpread")):
            home_point = -float(row["homeTeamSpread"])  # sign flip — see module docstring
            snaps.append(
                OddsSnapshot(
                    game_id=game_id, book="cfbfastr_consensus", snapshot_type="close",
                    captured_at=captured_at, market="spread", home_price=-110, away_price=-110,
                    home_point=home_point, away_point=-home_point,
                )
            )
        if pd.notna(row.get("overUnder")):
            total = float(row["overUnder"])
            snaps.append(
                OddsSnapshot(
                    game_id=game_id, book="cfbfastr_consensus", snapshot_type="close",
                    captured_at=captured_at, market="total", home_price=-110, away_price=-110,
                    home_point=total, away_point=total,
                )
            )
    return snaps


def _build_team_game_stats(pbp: pd.DataFrame) -> list[TeamGameStats]:
    if pbp.empty:
        return []
    df = pbp.copy()
    df["game_id"] = df["game_id"].astype(int).astype(str)
    df["success"] = df["EPA_success"].astype(float)
    df["is_pass"] = df["playType"].isin(PASS_PLAY_TYPES)
    df["is_rush"] = df["playType"].isin(RUSH_PLAY_TYPES)
    df["is_third_down"] = df["start.down"] == 3
    df["pressure"] = df["sack"].astype(bool)

    rows: list[TeamGameStats] = []
    for (game_id, team), grp in df.groupby(["game_id", "start.pos_team.name"]):
        if pd.isna(team):
            continue
        is_home = bool((grp["homeTeamName"] == team).iloc[0])
        pass_g = grp[grp["is_pass"]]
        rush_g = grp[grp["is_rush"]]
        third_downs = grp[grp["is_third_down"]]
        rows.append(
            TeamGameStats(
                game_id=game_id,
                team=str(team),
                is_home=is_home,
                epa_per_play=float(grp["EPA"].mean()) if len(grp) else None,
                success_rate=float(grp["success"].mean()) if len(grp) else None,
                pass_epa_per_play=float(pass_g["EPA"].mean()) if len(pass_g) else None,
                rush_epa_per_play=float(rush_g["EPA"].mean()) if len(rush_g) else None,
                third_down_pct=float(third_downs["first_down_created"].mean()) if len(third_downs) else None,
                pressure_rate=float(pass_g["pressure"].mean()) if len(pass_g) else None,
                # red_zone_pct intentionally omitted: cfbfastR's field-position
                # columns aren't in a directly-usable "yards to opponent's end
                # zone" form here, and getting the side-of-field logic wrong
                # would silently corrupt the feature — see module docstring.
            )
        )
    return rows


def build_ncaaf_dataset(years: list[int], repo_path: str) -> tuple[list[GameRecord], list[TeamGameStats], list[OddsSnapshot]]:
    repo = Path(repo_path)
    if not repo.exists():
        raise FileNotFoundError(
            f"cfbfastR-data checkout not found at {repo_path}. Clone it first:\n"
            "  GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 "
            "https://github.com/sportsdataverse/cfbfastr-data " + repo_path
        )
    schedules = _read_schedules(repo, years)
    pbp = _read_pbp(repo, years)
    games = _build_games(schedules)
    valid_ids = {g.game_id for g in games}
    stats = [s for s in _build_team_game_stats(pbp) if s.game_id in valid_ids]
    odds = [o for o in _build_odds(pbp) if o.game_id in valid_ids]
    return games, stats, odds

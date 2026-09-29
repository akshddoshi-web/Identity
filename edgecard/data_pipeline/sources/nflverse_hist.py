"""NFL history from nflverse (free, no key): schedules with real closing
prices, play-by-play aggregated to team-game level, weekly player stats,
snap counts, injuries, depth charts.

Everything lands in compact parquet files under a history directory
(`EDGECARD_HISTORY_DIR`, default data/history). In production those files
are built by the GitHub Actions ingest job and committed to the
`edgecard-data` branch, so neither the Streamlit app nor a laptop needs to
re-download ~30 MB of play-by-play per season.

games.csv conventions (nflverse): `spread_line` is the HOME team's expected
margin (positive = home favoured); `result` = home_score - away_score;
`home_spread_odds` is the price on the home side at that line; moneylines
and over/under odds are American prices. These are closing prices compiled
by nflverse — real vig included — which is what lets the backtest compare
against the no-vig closing line honestly.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from data_pipeline.config import REPO_ROOT

RELEASE = "https://github.com/nflverse/nflverse-data/releases/download"
GAMES_CSV = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
TRADES_CSV = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/trades.csv"
UA = {"User-Agent": "edgecard/1.0 (+https://github.com/akshddoshi-web/Identity)"}


def history_dir() -> Path:
    p = Path(os.environ.get("EDGECARD_HISTORY_DIR", REPO_ROOT / "data" / "history"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _get(url: str, timeout: int = 180) -> bytes:
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.content


def _read_parquet_url(url: str) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(_get(url)))


# --------------------------------------------------------------------------- #
# Schedules + closing prices
# --------------------------------------------------------------------------- #

def fetch_games() -> pd.DataFrame:
    local = os.environ.get("NFLDATA_DIR")
    if local and Path(local, "games.csv").exists():
        return pd.read_csv(Path(local, "games.csv"))
    return pd.read_csv(io.BytesIO(_get(GAMES_CSV)))


def fetch_trades() -> pd.DataFrame:
    local = os.environ.get("NFLDATA_DIR")
    if local and Path(local, "trades.csv").exists():
        return pd.read_csv(Path(local, "trades.csv"))
    return pd.read_csv(io.BytesIO(_get(TRADES_CSV)))


# --------------------------------------------------------------------------- #
# Play-by-play -> team-game aggregates
# --------------------------------------------------------------------------- #

PBP_KEEP = [
    "game_id", "season", "week", "posteam", "defteam", "home_team", "away_team", "epa", "success",
    "play_type", "special_teams_play", "pass_attempt", "rush_attempt", "qb_dropback", "sack", "qb_hit",
    "interception", "fumble", "fumble_lost", "yardline_100", "touchdown", "drive", "down", "pass_oe",
    "cpoe", "wp", "fixed_drive_result", "game_seconds_remaining",
]


def fetch_pbp(season: int) -> pd.DataFrame:
    df = _read_parquet_url(f"{RELEASE}/pbp/play_by_play_{season}.parquet")
    return df[[c for c in PBP_KEEP if c in df.columns]]


def team_game_stats_from_pbp(pbp: pd.DataFrame) -> pd.DataFrame:
    """One row per (game_id, team) with offensive AND defensive aggregates.
    Defensive columns are the opponent's offensive numbers in the same game.
    """
    p = pbp[pbp["posteam"].notna()].copy()
    scrim = p[p["play_type"].isin(["pass", "run"])]
    dropbacks = scrim[scrim.get("qb_dropback", 0) == 1]

    g = scrim.groupby(["game_id", "posteam"])
    off = pd.DataFrame({
        "plays": g.size(),
        "epa_play": g["epa"].mean(),
        "success_rate": g["success"].mean(),
        "pass_rate": g["pass_attempt"].mean() if "pass_attempt" in scrim else np.nan,
        "proe": g["pass_oe"].mean() if "pass_oe" in scrim else np.nan,
    })
    off["pass_epa"] = scrim[scrim["play_type"] == "pass"].groupby(["game_id", "posteam"])["epa"].mean()
    off["rush_epa"] = scrim[scrim["play_type"] == "run"].groupby(["game_id", "posteam"])["epa"].mean()
    db = dropbacks.groupby(["game_id", "posteam"])
    off["sack_rate"] = db["sack"].mean()
    pressured = ((dropbacks["sack"] == 1) | (dropbacks["qb_hit"] == 1)).astype(float)
    off["pressure_rate_allowed"] = pressured.groupby([dropbacks["game_id"], dropbacks["posteam"]]).mean()
    off["cpoe"] = dropbacks.groupby(["game_id", "posteam"])["cpoe"].mean() if "cpoe" in dropbacks else np.nan
    off["interceptions"] = g["interception"].sum()
    off["fumbles"] = g["fumble"].sum()
    off["fumbles_lost"] = g["fumble_lost"].sum()

    # red zone: share of drives that reached the 20 and ended in a TD
    if "drive" in p.columns and "fixed_drive_result" in p.columns:
        drv = p.groupby(["game_id", "posteam", "drive"]).agg(
            min_yl=("yardline_100", "min"), result=("fixed_drive_result", "last")
        ).reset_index()
        rz = drv[drv["min_yl"] <= 20]
        rz_g = rz.groupby(["game_id", "posteam"])
        off["rz_trips"] = rz_g.size()
        off["rz_td_rate"] = rz_g["result"].apply(lambda s: (s == "Touchdown").mean())
        off["drives"] = drv.groupby(["game_id", "posteam"]).size()

    # special teams EPA from the team's own perspective (as posteam minus as defteam)
    st = p[p.get("special_teams_play", 0) == 1]
    st_for = st.groupby(["game_id", "posteam"])["epa"].sum()
    st_against = st.groupby(["game_id", "defteam"])["epa"].sum()
    st_against.index = st_against.index.set_names(["game_id", "posteam"])
    off["st_epa"] = st_for.sub(st_against, fill_value=0)

    off = off.reset_index().rename(columns={"posteam": "team"})
    meta = p.groupby("game_id").agg(home_team=("home_team", "first"), away_team=("away_team", "first"),
                                    season=("season", "first"), week=("week", "first")).reset_index()
    off = off.merge(meta, on="game_id", how="left")
    off["is_home"] = (off["team"] == off["home_team"]).astype(int)
    off["opp"] = np.where(off["is_home"] == 1, off["away_team"], off["home_team"])

    stat_cols = [c for c in off.columns if c not in ("game_id", "team", "home_team", "away_team", "season",
                                                     "week", "is_home", "opp")]
    opp = off[["game_id", "team"] + stat_cols].rename(columns={"team": "opp", **{c: f"def_{c}" for c in stat_cols}})
    out = off.merge(opp, on=["game_id", "opp"], how="left")
    out["takeaways"] = out["def_interceptions"] + out["def_fumbles_lost"]
    out["giveaways"] = out["interceptions"] + out["fumbles_lost"]
    # fumble-recovery luck: lost fumbles beyond the ~50% league base rate
    out["fumble_luck"] = (out["def_fumbles_lost"] - 0.5 * out["def_fumbles"]) - (out["fumbles_lost"] - 0.5 * out["fumbles"])
    return out


# --------------------------------------------------------------------------- #
# Player-level
# --------------------------------------------------------------------------- #

def fetch_player_weeks(season: int) -> pd.DataFrame:
    for tag, name in (("stats_player", f"stats_player_week_{season}.parquet"),
                      ("player_stats", f"player_stats_{season}.parquet")):
        try:
            return _read_parquet_url(f"{RELEASE}/{tag}/{name}")
        except requests.HTTPError:
            continue
    raise RuntimeError(f"no weekly player stats file found for {season}")


def fetch_snap_counts(season: int) -> pd.DataFrame:
    return _read_parquet_url(f"{RELEASE}/snap_counts/snap_counts_{season}.parquet")


def fetch_injuries(season: int) -> pd.DataFrame:
    return _read_parquet_url(f"{RELEASE}/injuries/injuries_{season}.parquet")


def fetch_depth_charts(season: int) -> pd.DataFrame:
    return _read_parquet_url(f"{RELEASE}/depth_charts/depth_charts_{season}.parquet")


PLAYER_COLS = [
    "player_id", "player_display_name", "player_name", "position", "position_group", "team", "recent_team",
    "season", "week", "season_type", "opponent_team", "completions", "attempts", "passing_yards", "passing_tds",
    "passing_interceptions", "interceptions", "sacks_suffered", "carries", "rushing_yards", "rushing_tds",
    "receptions", "targets", "receiving_yards", "receiving_tds", "target_share", "air_yards_share", "wopr",
]


def slim_player_weeks(df: pd.DataFrame) -> pd.DataFrame:
    d = df[[c for c in PLAYER_COLS if c in df.columns]].copy()
    if "team" not in d.columns and "recent_team" in d.columns:
        d = d.rename(columns={"recent_team": "team"})
    elif "recent_team" in d.columns:
        d = d.drop(columns=["recent_team"])
    if "passing_interceptions" in d.columns and "interceptions" in d.columns:
        d = d.drop(columns=["interceptions"])
    d = d.rename(columns={"passing_interceptions": "interceptions", "player_display_name": "player"})
    if "player" not in d.columns and "player_name" in d.columns:
        d = d.rename(columns={"player_name": "player"})
    return d


SNAP_COLS = ["game_id", "season", "week", "player", "pfr_player_id", "position", "team", "opponent",
             "offense_snaps", "offense_pct", "defense_snaps", "defense_pct"]


def build_history(seasons: list[int], out_dir: Path | None = None, include_pbp: bool = True) -> dict[str, int]:
    """Downloads everything for `seasons` and writes parquet files. Returns
    {file: rows}. Per-season failures are reported, not raised, so one
    missing asset (e.g. a season whose snap counts aren't published yet)
    doesn't block the rest."""
    out = out_dir or history_dir()
    written: dict[str, int] = {}

    games = fetch_games()
    games.to_parquet(out / "nfl_games.parquet", index=False)
    written["nfl_games"] = len(games)
    try:
        trades = fetch_trades()
        trades.to_parquet(out / "nfl_trades.parquet", index=False)
        written["nfl_trades"] = len(trades)
    except Exception as exc:  # noqa: BLE001
        print(f"  trades: {exc}")

    tg, pw, sc, inj = [], [], [], []
    for s in seasons:
        if include_pbp:
            try:
                tg.append(team_game_stats_from_pbp(fetch_pbp(s)))
                print(f"  {s} pbp -> team games ok")
            except Exception as exc:  # noqa: BLE001
                print(f"  {s} pbp FAILED: {exc}")
        for name, fn, bucket in (("player weeks", lambda y: slim_player_weeks(fetch_player_weeks(y)), pw),
                                 ("snap counts", lambda y: fetch_snap_counts(y)[[c for c in SNAP_COLS]], sc),
                                 ("injuries", fetch_injuries, inj)):
            try:
                bucket.append(fn(s))
            except Exception as exc:  # noqa: BLE001
                print(f"  {s} {name} FAILED: {exc}")

    for name, frames in (("nfl_team_games", tg), ("nfl_player_weeks", pw), ("nfl_snaps", sc), ("nfl_injuries", inj)):
        if frames:
            df = pd.concat(frames, ignore_index=True)
            df.to_parquet(out / f"{name}.parquet", index=False)
            written[name] = len(df)
    try:
        latest = max(seasons)
        dc = fetch_depth_charts(latest)
        dc.to_parquet(out / "nfl_depth_latest.parquet", index=False)
        written["nfl_depth_latest"] = len(dc)
    except Exception as exc:  # noqa: BLE001
        print(f"  depth charts FAILED: {exc}")
    return written


def load(name: str) -> pd.DataFrame:
    """Reads one history parquet (e.g. 'nfl_games'). Falls back to building
    nfl_games from games.csv if only that is missing."""
    path = history_dir() / f"{name}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    if name == "nfl_games":
        return fetch_games()
    raise FileNotFoundError(f"{path} not found — run `edgecard ingest --league nfl` (or fetch the edgecard-data branch)")

"""Advanced/efficiency stats ingestion (EPA, success rate, DVOA-style ratings for
NFL/NCAAF; four-factors + on/off ratings for NBA).

Real sourcing notes:
  - NFL/NCAAF EPA & success rate are computed from play-by-play, not looked up.
    nflfastR/cfbfastR publish play-by-play with an `epa` column per play already
    computed; success_rate is typically defined as EPA > 0 (or a down-distance
    adjusted threshold). Aggregate to team-game level: mean EPA/play, share of
    plays with epa>0, split by pass/rush, red zone trips scored / red zone
    trips, third-down conversions / attempts, and pressure rate (pressures /
    dropbacks — requires PFF or nflfastR's `qb_hit`/`sack` proxy if you don't
    have PFF access). PFF grades themselves require a PFF Elite/PFF+ API
    subscription — this repo cannot include or fetch them; if you have access,
    populate `pff_off_grade`/`pff_def_grade` directly.
  - NBA advanced stats (ORtg/DRtg/pace/eFG%/TOV%/ORB%/FTr) come straight off
    stats.nba.com's `leaguedashteamstats` (Advanced measure type) via nba_api,
    at the team-game level use `boxscoreadvancedv2`. Lineup net ratings come
    from `leaguedashlineups`, weighted by projected available minutes for
    tonight's rotation (which is where the injury report feeds in — see
    `injury_adjusted_lineup_rating` below).

This module ships an `EPACalculator` that computes EPA-style team-game
aggregates from a raw play-by-play DataFrame you supply (any source), because
that computation is source-agnostic once you have plays with a `epa` column,
`posteam`, `game_id`, `down`, `play_type` etc. — the standard nflfastR/
cfbfastR shape.
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict

import pandas as pd

from data_pipeline.db import connect
from data_pipeline.schema import TeamGameStats


class EPACalculator:
    """Aggregates nflfastR/cfbfastR-shaped play-by-play into team-game
    TeamGameStats rows. Expects columns:
      game_id, posteam, home_team, epa, success (0/1), play_type
      ('pass'/'run'/other), down, yardline_100, third_down_converted (0/1),
      pressure (0/1, optional).
    """

    REQUIRED_COLS = {"game_id", "posteam", "home_team", "epa", "play_type", "down"}

    def compute(self, pbp: pd.DataFrame) -> list[TeamGameStats]:
        missing = self.REQUIRED_COLS - set(pbp.columns)
        if missing:
            raise ValueError(f"play-by-play frame missing required columns: {missing}")

        pbp = pbp.copy()
        if "success" not in pbp.columns:
            pbp["success"] = (pbp["epa"] > 0).astype(int)

        out: list[TeamGameStats] = []
        for (game_id, team), g in pbp.groupby(["game_id", "posteam"]):
            is_home = bool((g["home_team"] == team).iloc[0]) if "home_team" in g else False
            pass_g = g[g["play_type"] == "pass"]
            rush_g = g[g["play_type"] == "run"]
            third_downs = g[g["down"] == 3]
            red_zone = g[g.get("yardline_100", pd.Series(dtype=float)) <= 20] if "yardline_100" in g else g.iloc[0:0]

            row = TeamGameStats(
                game_id=str(game_id),
                team=str(team),
                is_home=is_home,
                epa_per_play=float(g["epa"].mean()) if len(g) else None,
                success_rate=float(g["success"].mean()) if len(g) else None,
                pass_epa_per_play=float(pass_g["epa"].mean()) if len(pass_g) else None,
                rush_epa_per_play=float(rush_g["epa"].mean()) if len(rush_g) else None,
                third_down_pct=float(third_downs["third_down_converted"].mean())
                if "third_down_converted" in third_downs and len(third_downs)
                else None,
                red_zone_pct=float(red_zone["success"].mean()) if len(red_zone) else None,
                pressure_rate=float(pass_g["pressure"].mean())
                if "pressure" in pass_g and len(pass_g)
                else None,
            )
            out.append(row)
        return out


def injury_adjusted_lineup_rating(
    base_lineup_net_rating: float, injuries: list[dict], impact_weight: float = 1.0
) -> float:
    """Simple, transparent injury-adjustment heuristic for NBA lineup net
    rating: subtract each missing/limited player's `impact_score` (0-1,
    typically derived from their on/off net rating swing or usage%), scaled
    by `impact_weight` (a configurable dampener since impact scores from
    box-score-derived on/off splits are noisy in small samples).

    This is intentionally simple and documented as a heuristic, not a causal
    estimate — replace with a regression-based RAPM/BPM adjustment if you
    have the play-by-play lineup data to support it.
    """
    penalty = sum(i.get("impact_score", 0.0) or 0.0 for i in injuries if i.get("status") in ("out", "doubtful"))
    return base_lineup_net_rating - impact_weight * penalty


def upsert_team_game_stats(rows: list[TeamGameStats], conn: sqlite3.Connection | None = None) -> int:
    def _write(c: sqlite3.Connection):
        n = 0
        for r in rows:
            d = asdict(r)
            d["is_home"] = int(d["is_home"])
            cols = ", ".join(d.keys())
            placeholders = ", ".join(f":{k}" for k in d.keys())
            c.execute(
                f"INSERT OR REPLACE INTO team_game_stats ({cols}) VALUES ({placeholders})", d
            )
            n += 1
        return n

    if conn is not None:
        return _write(conn)
    with connect() as c:
        return _write(c)

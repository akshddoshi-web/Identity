"""Historical game / schedule / injury ingestion.

This module defines the *interface* your real data sources plug into:
`GameSource` for schedules+scores+context (rest, travel, weather, referees)
and `InjurySource` for injury reports. It ships one concrete implementation,
`CSVGameSource`, because the actual providers (nflfastR/cfbfastR/nba_api/
SportsDataIO) each have their own client libraries and licensing terms this
repo can't redistribute.

To wire in real data:
  - NFL/NCAAF: pull schedules from nflfastR (`nflreadpy`/`nfl_data_py`) or
    cfbfastR (R, or their published CSV/parquet releases), export to CSV in
    the shape below, then use CSVGameSource. Rest days/travel distance can
    be derived from the schedule (days since last game; great-circle
    distance between team home coordinates, which you'll need to supply).
  - NBA: nba_api's `leaguegamefinder`/`scoreboardv2` endpoints, or
    SportsDataIO's schedule API (needs `SPORTSDATAIO_API_KEY`).

All ingestion writes go through `upsert_games` / `upsert_injuries`, which are
idempotent (safe to re-run) via `INSERT OR REPLACE` on the natural key.
"""
from __future__ import annotations

import csv
import sqlite3
from dataclasses import asdict
from pathlib import Path

from data_pipeline.db import connect
from data_pipeline.schema import GameRecord, InjuryRecord


class GameSource:
    """Interface: yields GameRecord objects. Subclass for a real provider."""

    def fetch(self) -> list[GameRecord]:
        raise NotImplementedError


class InjurySource:
    def fetch(self) -> list[InjuryRecord]:
        raise NotImplementedError


class CSVGameSource(GameSource):
    """Reads games from a CSV with headers matching GameRecord field names.

    Booleans should be 0/1, missing numeric fields blank.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def fetch(self) -> list[GameRecord]:
        out: list[GameRecord] = []
        with open(self.path, newline="") as f:
            for row in csv.DictReader(f):
                out.append(
                    GameRecord(
                        game_id=row["game_id"],
                        sport=row["sport"],
                        season=int(row["season"]),
                        week=int(row["week"]) if row.get("week") else None,
                        game_date=row["game_date"],
                        home_team=row["home_team"],
                        away_team=row["away_team"],
                        home_score=_int_or_none(row.get("home_score")),
                        away_score=_int_or_none(row.get("away_score")),
                        is_final=bool(int(row.get("is_final") or 0)),
                        neutral_site=bool(int(row.get("neutral_site") or 0)),
                        home_rest_days=_int_or_none(row.get("home_rest_days")),
                        away_rest_days=_int_or_none(row.get("away_rest_days")),
                        home_travel_mi=_float_or_none(row.get("home_travel_mi")),
                        away_travel_mi=_float_or_none(row.get("away_travel_mi")),
                        referee_crew=row.get("referee_crew") or None,
                        weather_temp_f=_float_or_none(row.get("weather_temp_f")),
                        weather_wind_mph=_float_or_none(row.get("weather_wind_mph")),
                        weather_precip=row.get("weather_precip") or None,
                        is_dome=bool(int(row.get("is_dome") or 0)),
                    )
                )
        return out


def _int_or_none(v):
    return int(v) if v not in (None, "") else None


def _float_or_none(v):
    return float(v) if v not in (None, "") else None


def upsert_games(games: list[GameRecord], conn: sqlite3.Connection | None = None) -> int:
    def _write(c: sqlite3.Connection):
        n = 0
        for g in games:
            d = asdict(g)
            d["is_final"] = int(d["is_final"])
            d["neutral_site"] = int(d["neutral_site"])
            d["is_dome"] = int(d["is_dome"])
            cols = ", ".join(d.keys())
            placeholders = ", ".join(f":{k}" for k in d.keys())
            c.execute(f"INSERT OR REPLACE INTO games ({cols}) VALUES ({placeholders})", d)
            n += 1
        return n

    if conn is not None:
        return _write(conn)
    with connect() as c:
        return _write(c)


def upsert_injuries(injuries: list[InjuryRecord], conn: sqlite3.Connection | None = None) -> int:
    def _write(c: sqlite3.Connection):
        n = 0
        for inj in injuries:
            d = asdict(inj)
            cols = ", ".join(d.keys())
            placeholders = ", ".join(f":{k}" for k in d.keys())
            c.execute(f"INSERT INTO injuries ({cols}) VALUES ({placeholders})", d)
            n += 1
        return n

    if conn is not None:
        return _write(conn)
    with connect() as c:
        return _write(c)


def ingest_from_csv(games_csv: str | Path) -> int:
    source = CSVGameSource(games_csv)
    games = source.fetch()
    return upsert_games(games)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest historical games from a CSV export.")
    parser.add_argument("csv_path", help="Path to a CSV matching the GameRecord schema.")
    args = parser.parse_args()
    n = ingest_from_csv(args.csv_path)
    print(f"Upserted {n} games from {args.csv_path}")

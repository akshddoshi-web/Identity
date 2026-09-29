"""Typed records for the data pipeline. Plain dataclasses (not pandera/pydantic) to
keep the dependency footprint small — validation happens at insert time in db writers.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GameRecord:
    game_id: str
    sport: str                 # NFL | NCAAF | NBA
    season: int
    game_date: str              # ISO date/time
    home_team: str
    away_team: str
    week: int | None = None
    home_score: int | None = None
    away_score: int | None = None
    is_final: bool = False
    neutral_site: bool = False
    home_rest_days: int | None = None
    away_rest_days: int | None = None
    home_travel_mi: float | None = None
    away_travel_mi: float | None = None
    referee_crew: str | None = None
    weather_temp_f: float | None = None
    weather_wind_mph: float | None = None
    weather_precip: str | None = None
    is_dome: bool = False


@dataclass
class InjuryRecord:
    game_id: str
    team: str
    player: str
    status: str                # out | doubtful | questionable | probable
    position: str | None = None
    impact_score: float | None = None
    report_date: str | None = None


@dataclass
class TeamGameStats:
    """One row per team per game. Football fields populated for NFL/NCAAF,
    basketball fields populated for NBA; the unused half stays None."""

    game_id: str
    team: str
    is_home: bool
    # football
    epa_per_play: float | None = None
    success_rate: float | None = None
    pass_epa_per_play: float | None = None
    rush_epa_per_play: float | None = None
    red_zone_pct: float | None = None
    third_down_pct: float | None = None
    pressure_rate: float | None = None
    pff_off_grade: float | None = None
    pff_def_grade: float | None = None
    # basketball
    off_rating: float | None = None
    def_rating: float | None = None
    pace: float | None = None
    efg_pct: float | None = None
    tov_pct: float | None = None
    orb_pct: float | None = None
    ftr: float | None = None
    net_rating_lineup_wtd: float | None = None


@dataclass
class OddsSnapshot:
    game_id: str
    book: str
    snapshot_type: str          # open | close | live
    captured_at: str
    market: str                  # spread | total | moneyline
    home_price: float | None = None
    away_price: float | None = None
    home_point: float | None = None
    away_point: float | None = None

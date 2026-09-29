"""Home venues for every NFL and NBA team: coordinates, time zone, altitude,
roof type. Used for travel miles, time zones crossed, altitude games, and to
decide whether weather matters (weather is only fetched for outdoor venues).

Team keys are the abbreviations nflverse (NFL) and nba.com (NBA) use.
ESPN spells several differently; `canonical_team` maps them.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Venue:
    lat: float
    lon: float
    tz: str
    altitude_ft: float
    roof: str  # outdoors | dome | retractable


NFL_VENUES: dict[str, Venue] = {
    "ARI": Venue(33.5276, -112.2626, "America/Phoenix", 1070, "retractable"),
    "ATL": Venue(33.7554, -84.4008, "America/New_York", 1050, "retractable"),
    "BAL": Venue(39.2780, -76.6227, "America/New_York", 30, "outdoors"),
    "BUF": Venue(42.7738, -78.7870, "America/New_York", 600, "outdoors"),
    "CAR": Venue(35.2258, -80.8528, "America/New_York", 750, "outdoors"),
    "CHI": Venue(41.8623, -87.6167, "America/Chicago", 590, "outdoors"),
    "CIN": Venue(39.0955, -84.5160, "America/New_York", 490, "outdoors"),
    "CLE": Venue(41.5061, -81.6995, "America/New_York", 580, "outdoors"),
    "DAL": Venue(32.7473, -97.0945, "America/Chicago", 550, "retractable"),
    "DEN": Venue(39.7439, -105.0201, "America/Denver", 5280, "outdoors"),
    "DET": Venue(42.3400, -83.0456, "America/Detroit", 600, "dome"),
    "GB": Venue(44.5013, -88.0622, "America/Chicago", 640, "outdoors"),
    "HOU": Venue(29.6847, -95.4107, "America/Chicago", 50, "retractable"),
    "IND": Venue(39.7601, -86.1639, "America/Indiana/Indianapolis", 715, "retractable"),
    "JAX": Venue(30.3239, -81.6373, "America/New_York", 15, "outdoors"),
    "KC": Venue(39.0489, -94.4839, "America/Chicago", 750, "outdoors"),
    "LA": Venue(33.9535, -118.3392, "America/Los_Angeles", 100, "dome"),
    "LAC": Venue(33.9535, -118.3392, "America/Los_Angeles", 100, "dome"),
    "LV": Venue(36.0909, -115.1833, "America/Los_Angeles", 2030, "dome"),
    "MIA": Venue(25.9580, -80.2389, "America/New_York", 10, "outdoors"),
    "MIN": Venue(44.9736, -93.2575, "America/Chicago", 830, "dome"),
    "NE": Venue(42.0909, -71.2643, "America/New_York", 290, "outdoors"),
    "NO": Venue(29.9509, -90.0815, "America/Chicago", 5, "dome"),
    "NYG": Venue(40.8135, -74.0745, "America/New_York", 10, "outdoors"),
    "NYJ": Venue(40.8135, -74.0745, "America/New_York", 10, "outdoors"),
    "PHI": Venue(39.9008, -75.1675, "America/New_York", 30, "outdoors"),
    "PIT": Venue(40.4468, -80.0158, "America/New_York", 730, "outdoors"),
    "SEA": Venue(47.5952, -122.3316, "America/Los_Angeles", 20, "outdoors"),
    "SF": Venue(37.4033, -121.9694, "America/Los_Angeles", 10, "outdoors"),
    "TB": Venue(27.9759, -82.5033, "America/New_York", 30, "outdoors"),
    "TEN": Venue(36.1665, -86.7713, "America/Chicago", 400, "outdoors"),
    "WAS": Venue(38.9077, -76.8645, "America/New_York", 200, "outdoors"),
    # historical franchises still present in older nflverse seasons
    "OAK": Venue(37.7516, -122.2005, "America/Los_Angeles", 10, "outdoors"),
    "SD": Venue(32.7831, -117.1196, "America/Los_Angeles", 100, "outdoors"),
    "STL": Venue(38.6328, -90.1885, "America/Chicago", 460, "dome"),
}

NBA_VENUES: dict[str, Venue] = {
    "ATL": Venue(33.7573, -84.3963, "America/New_York", 1050, "dome"),
    "BOS": Venue(42.3662, -71.0621, "America/New_York", 20, "dome"),
    "BKN": Venue(40.6826, -73.9754, "America/New_York", 30, "dome"),
    "CHA": Venue(35.2251, -80.8392, "America/New_York", 750, "dome"),
    "CHI": Venue(41.8807, -87.6742, "America/Chicago", 590, "dome"),
    "CLE": Venue(41.4965, -81.6882, "America/New_York", 650, "dome"),
    "DAL": Venue(32.7905, -96.8103, "America/Chicago", 430, "dome"),
    "DEN": Venue(39.7487, -105.0077, "America/Denver", 5280, "dome"),
    "DET": Venue(42.3410, -83.0550, "America/Detroit", 600, "dome"),
    "GSW": Venue(37.7680, -122.3877, "America/Los_Angeles", 10, "dome"),
    "HOU": Venue(29.7508, -95.3621, "America/Chicago", 50, "dome"),
    "IND": Venue(39.7640, -86.1555, "America/Indiana/Indianapolis", 715, "dome"),
    "LAC": Venue(33.9447, -118.3417, "America/Los_Angeles", 100, "dome"),
    "LAL": Venue(34.0430, -118.2673, "America/Los_Angeles", 300, "dome"),
    "MEM": Venue(35.1382, -90.0506, "America/Chicago", 260, "dome"),
    "MIA": Venue(25.7814, -80.1870, "America/New_York", 10, "dome"),
    "MIL": Venue(43.0451, -87.9172, "America/Chicago", 620, "dome"),
    "MIN": Venue(44.9795, -93.2761, "America/Chicago", 830, "dome"),
    "NOP": Venue(29.9490, -90.0821, "America/Chicago", 5, "dome"),
    "NYK": Venue(40.7505, -73.9934, "America/New_York", 30, "dome"),
    "OKC": Venue(35.4634, -97.5151, "America/Chicago", 1200, "dome"),
    "ORL": Venue(28.5392, -81.3839, "America/New_York", 100, "dome"),
    "PHI": Venue(39.9012, -75.1720, "America/New_York", 30, "dome"),
    "PHX": Venue(33.4457, -112.0712, "America/Phoenix", 1090, "dome"),
    "POR": Venue(45.5316, -122.6668, "America/Los_Angeles", 50, "dome"),
    "SAC": Venue(38.5802, -121.4997, "America/Los_Angeles", 30, "dome"),
    "SAS": Venue(29.4270, -98.4375, "America/Chicago", 650, "dome"),
    "TOR": Venue(43.6435, -79.3791, "America/Toronto", 250, "dome"),
    "UTA": Venue(40.7683, -111.9011, "America/Denver", 4226, "dome"),
    "WAS": Venue(38.8981, -77.0209, "America/New_York", 30, "dome"),
}

# ESPN (and a few other feeds) spell some teams differently.
_ALIASES = {
    "NFL": {"WSH": "WAS", "LAR": "LA", "JAC": "JAX", "OAK": "LV"},
    "NBA": {"GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS",
            "PHO": "PHX", "BRK": "BKN", "CHO": "CHA", "NJ": "BKN"},
}


def venues(league: str) -> dict[str, Venue]:
    return NFL_VENUES if league == "NFL" else NBA_VENUES


def canonical_team(league: str, abbr: str, *, keep_historical: bool = False) -> str:
    """Maps a feed's abbreviation onto this repo's canonical one. OAK is
    only rewritten to LV for live feeds; historical nflverse rows keep OAK
    (pass keep_historical=True) so old seasons stay in the right city."""
    a = abbr.upper()
    if keep_historical and a in venues(league):
        return a
    return _ALIASES.get(league, {}).get(a, a)


def haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def utc_offset_hours(tz: str, when: dt.datetime | None = None) -> float:
    when = when or dt.datetime(2025, 1, 15)
    return ZoneInfo(tz).utcoffset(when).total_seconds() / 3600.0


def is_weather_exposed(league: str, home_team: str) -> bool:
    """Weather only matters outdoors. Retractable roofs are treated as closed
    in bad weather (the usual practice), so they count as sheltered."""
    if league != "NFL":
        return False
    v = NFL_VENUES.get(home_team)
    return bool(v and v.roof == "outdoors")

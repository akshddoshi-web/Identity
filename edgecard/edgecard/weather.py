"""Game-time weather for outdoor NFL venues from Open-Meteo (free, no key).

Historical games use nflverse's recorded temp/wind. For upcoming games the
forecast for the kickoff hour replaces those features, so the model sees
the same kind of input live that it was trained on.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import requests

from data_pipeline.venues import NFL_VENUES
from edgecard.freshness import record

FORECAST = "https://api.open-meteo.com/v1/forecast"


def kickoff_forecast(team: str, kickoff_utc: pd.Timestamp) -> dict | None:
    v = NFL_VENUES.get(team)
    if v is None or v.roof != "outdoors":
        return None
    try:
        r = requests.get(FORECAST, params={
            "latitude": v.lat, "longitude": v.lon, "hourly": "temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m",
            "wind_speed_unit": "mph", "temperature_unit": "fahrenheit", "timezone": "UTC", "forecast_days": 8}, timeout=20)
        r.raise_for_status()
        h = r.json()["hourly"]
    except (requests.RequestException, KeyError, ValueError):
        return None
    times = pd.to_datetime(h["time"], utc=True)
    idx = int(np.argmin(np.abs((times - kickoff_utc).total_seconds())))
    return {"temp_f": h["temperature_2m"][idx], "wind_mph": h["wind_speed_10m"][idx], "gust_mph": h["wind_gusts_10m"][idx],
            "precip_mm": h["precipitation"][idx], "forecast_hour": str(times[idx])}


def apply_forecast_weather(frame: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Overwrites wx_* features of upcoming games with the kickoff forecast."""
    f = frame.copy()
    n_ok = 0
    for _, ev in events.iterrows():
        ko = pd.Timestamp(ev["commence_time"])
        ko = ko.tz_localize("UTC") if ko.tzinfo is None else ko.tz_convert("UTC")
        m = (~f["is_final"]) & (f["home_team"] == ev["home_team"]) & (f["away_team"] == ev["away_team"])
        if not m.any():
            continue
        wx = kickoff_forecast(ev["home_team"], ko)
        if wx is None:
            continue
        n_ok += 1
        f.loc[m, "wx_wind"] = wx["wind_mph"]
        f.loc[m, "wx_temp_cold"] = max(0.0, 40.0 - wx["temp_f"])
        f.loc[m, "wx_outdoor"] = 1.0
    record("nfl.open_meteo.forecast", ok=n_ok > 0 or events.empty, n=n_ok, note="outdoor venues only")
    return f

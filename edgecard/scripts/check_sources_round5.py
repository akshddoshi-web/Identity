"""Round-5 probe: ESPN NFL scoreboard date-range behaviour + fetch_events."""
import json

import requests

base = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
for q in ["", "?dates=20260929-20261006&limit=100", "?dates=20261001", "?week=4&seasontype=2&dates=2026", "?seasontype=2&week=4"]:
    r = requests.get(base + q, timeout=20)
    d = r.json() if r.ok else {}
    ev = d.get("events", [])
    print(r.status_code, q, "events:", len(ev), [(e["date"], e["shortName"], e["competitions"][0]["status"]["type"]["state"]) for e in ev[:3]])
nba = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
for q in ["?dates=20251001-20251031&limit=1000", "?dates=20241022-20241130&limit=1000", "?dates=20261002"]:
    r = requests.get(nba + q, timeout=30)
    d = r.json() if r.ok else {}
    ev = d.get("events", [])
    print("NBA", r.status_code, q, "events:", len(ev), ev[0]["season"] if ev else None,
          json.dumps((ev[0]["competitions"][0].get("odds") or [None])[0])[:700] if ev else "")
import sys
sys.path.insert(0, ".")
from edgecard.odds import fetch_events  # noqa: E402

evs = fetch_events("NFL")
print("fetch_events NFL:", len(evs), [(e.game_key, e.status) for e in evs[:5]])

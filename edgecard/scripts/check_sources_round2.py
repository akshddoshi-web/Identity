"""Second-round probe: which ESPN / NBA CDN host+header combinations work
from GitHub runners, plus free odds alternatives. Prints the first bytes of
any 403 body so we can tell a WAF block from an auth error."""
from __future__ import annotations

import json
import subprocess

import requests

BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
VARIANTS = {
    "none": {},
    "browser": BROWSER,
    "browser+ref": {**BROWSER, "Referer": "https://www.espn.com/", "Origin": "https://www.espn.com", "Accept": "application/json"},
    "curl-ua": {"User-Agent": "curl/8.5.0"},
}


def probe(name, url, variants=("none", "browser", "browser+ref", "curl-ua"), show=0):
    for v in variants:
        try:
            r = requests.get(url, headers=VARIANTS[v], timeout=15)
            body = r.text[:200].replace("\n", " ") if r.status_code != 200 else ""
            print(f"{'OK  ' if r.ok else 'FAIL'} {name:<40} [{v:<11}] {r.status_code} {len(r.content):>8}B {body}", flush=True)
            if r.ok:
                if show:
                    try:
                        print("   ", json.dumps(r.json())[:show])
                    except ValueError:
                        print("   ", r.text[:show])
                return r
        except requests.RequestException as e:
            print(f"FAIL {name:<40} [{v:<11}] {type(e).__name__}")
    # also try real curl binary (different TLS fingerprint)
    out = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "-m", "15", url], capture_output=True, text=True)
    print(f"     {name:<40} [curl-binary] {out.stdout} {out.stderr[:100]}")
    return None


ESPN_PATHS = [
    "football/nfl/scoreboard",
    "basketball/nba/scoreboard",
    "football/nfl/injuries",
]
for host in ["site.api.espn.com", "site.web.api.espn.com"]:
    for p in ESPN_PATHS:
        probe(f"{host}/{p}", f"https://{host}/apis/site/v2/sports/{p}")
probe("cdn.espn.com core scoreboard", "https://cdn.espn.com/core/nfl/scoreboard?xhr=1")
sb = probe("core.api nfl events", "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events?limit=5", show=800)
ev = None
if sb is not None:
    items = sb.json().get("items", [])
    if items:
        ev = items[0]["$ref"].split("/events/")[1].split("?")[0]
if ev:
    base = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{ev}/competitions/{ev}"
    o = probe("core.api odds", f"{base}/odds?limit=50")
    if o is not None:
        items = o.json().get("items", [])
        print("   providers:", [(i.get("provider", {}).get("id"), i.get("provider", {}).get("name")) for i in items])
        if items:
            print("   provider0:", json.dumps(items[0])[:3000])
            for it in items[:4]:
                pid = it.get("provider", {}).get("id")
                probe(f"core.api propBets p{pid}", f"{base}/odds/{pid}/propBets?limit=1000", variants=("none",), show=3000)
    probe("core.api injuries(team 12)", "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/teams/12/injuries?limit=50", show=600)
    probe("site.web summary", f"https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={ev}", show=300)

probe("site.web nfl scoreboard(web)", "https://site.web.api.espn.com/apis/v2/scoreboard/header?sport=football&league=nfl", show=1500)
probe("site.web nfl news", "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=3")

nba_hdr = {**BROWSER, "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com", "Accept": "application/json"}
VARIANTS["nba"] = nba_hdr
for u in ["https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
          "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_0022400001.json"]:
    probe("cdn.nba " + u.rsplit("/", 1)[1], u, variants=("none", "browser", "nba", "curl-ua"))

# Free NBA alternatives
probe("pbpstats api", "https://api.pbpstats.com/get-games/nba?Season=2024-25&SeasonType=Regular%2BSeason", show=400)
probe("bbref box score", "https://www.basketball-reference.com/boxscores/202410220BOS.html", variants=("browser",))

# Free odds alternatives (public JSON, no key)
probe("actionnetwork nfl scoreboard", "https://api.actionnetwork.com/web/v1/scoreboard/nfl?period=game", show=2500)
probe("kalshi public markets", "https://api.elections.kalshi.com/trade-api/v2/markets?limit=3&series_ticker=KXNFLGAME", show=1500)
probe("polymarket gamma nfl", "https://gamma-api.polymarket.com/events?tag_slug=nfl&closed=false&limit=2", show=1500)

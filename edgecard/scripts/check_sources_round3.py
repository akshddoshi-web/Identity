"""Round-3 probe: shapes needed to write parsers (prop prices, multi-book
odds, historical open/close availability)."""
from __future__ import annotations

import collections
import json

import requests

S = requests.Session()  # no custom UA: ESPN 403s browser-looking UAs from cloud IPs


def get(url, **kw):
    r = S.get(url, timeout=20, **kw)
    print(f"{r.status_code} {len(r.content):>8}B {url[:150]}", flush=True)
    return r.json() if r.ok else None


CORE = "https://sports.core.api.espn.com/v2/sports"

# 1) ESPN propBets: all keys present, and whether any price fields exist
ev = "401872963"
pb = get(f"{CORE}/football/leagues/nfl/events/{ev}/competitions/{ev}/odds/100/propBets?limit=1000")
if pb:
    keyset = collections.Counter()
    for it in pb["items"]:
        for k, v in it.items():
            keyset[k] += 1
            if isinstance(v, dict):
                for k2 in v:
                    keyset[f"{k}.{k2}"] += 1
    print("propBets key counts:", dict(keyset))
    types = collections.Counter(it["type"]["name"] for it in pb["items"])
    print("prop types:", dict(types))
    withodds = [it for it in pb["items"] if any(k not in ("competition", "athlete", "provider", "type", "lastUpdated", "current", "open") for k in it)]
    print("items with extra keys:", len(withodds), json.dumps(withodds[:2])[:2500])
    print("item0 full:", json.dumps(pb["items"][0])[:1500])
    print("item1 full:", json.dumps(pb["items"][1])[:1500])

# 2) ESPN historical odds: an NFL game from 2022 and an NBA game from 2024
for league, sport, date in (("nfl", "football", "20221016"), ("nba", "basketball", "20240115"), ("nba", "basketball", "20190115")):
    sb = get(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={date}")
    if sb and sb.get("events"):
        e = sb["events"][0]["id"]
        o = get(f"{CORE}/{sport}/leagues/{league}/events/{e}/competitions/{e}/odds?limit=50")
        if o:
            for it in o.get("items", [])[:6]:
                ho = it.get("homeTeamOdds", {})
                print(f"   {league} {date} provider={it.get('provider', {}).get('name')} spread={it.get('spread')} ou={it.get('overUnder')} "
                      f"home_ml={ho.get('moneyLine')} open={json.dumps(ho.get('open'))[:300]} close={json.dumps(ho.get('close'))[:200]}")

# 3) ESPN NBA summary: player box scores present?
nsb = get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20250301")
if nsb and nsb.get("events"):
    e = nsb["events"][0]["id"]
    s = get(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={e}")
    if s:
        print("   nba summary keys:", list(s.keys()))
        bs = s.get("boxscore", {}).get("players", [])
        if bs:
            st = bs[0]["statistics"][0]
            print("   nba player stat labels:", st.get("labels") or st.get("names"))
            print("   first athlete row:", json.dumps(st["athletes"][0])[:600])

# 4) Action Network: odds structure + book ids, props endpoints
an = get("https://api.actionnetwork.com/web/v1/scoreboard/nfl?period=game&bookIds=15,30,68,69,71,75,79,123,247,280,972")
if an:
    g = an["games"][0]
    print("   AN game keys:", list(g.keys()))
    print("   AN odds sample:", json.dumps(g.get("odds", [])[:3])[:2500])
    books = collections.Counter(o.get("book_id") for gg in an["games"] for o in gg.get("odds", []))
    print("   AN book ids:", dict(books))
for u in [
    "https://api.actionnetwork.com/web/v1/books",
    "https://api.actionnetwork.com/web/v2/scoreboard/nfl/markets?bookIds=15,30,68,69,71,75,79&periods=event",
    f"https://api.actionnetwork.com/web/v1/games/{an['games'][0]['id']}/props" if an else "",
    "https://api.actionnetwork.com/web/v1/leagues/1/props/core_bet_type_9_passing_yards?bookIds=15,30,68,69,71,75,79",
]:
    if not u:
        continue
    d = get(u)
    if d is not None:
        print("   ", json.dumps(d)[:1800])

# 5) pbpstats: lineup / on-off availability
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
for u in [
    "https://api.pbpstats.com/get-totals/nba?Season=2024-25&SeasonType=Regular%2BSeason&Type=Team",
    "https://api.pbpstats.com/get-totals/nba?Season=2024-25&SeasonType=Regular%2BSeason&Type=Lineup&TeamId=1610612738",
    "https://api.pbpstats.com/get-wowy-stats/nba?Season=2024-25&SeasonType=Regular%2BSeason&TeamId=1610612738&Type=Player&0Exactly1OnFloor=1628369",
    "https://api.pbpstats.com/get-game-logs/nba?Season=2024-25&SeasonType=Regular%2BSeason&EntityType=Team&EntityId=1610612738",
]:
    try:
        r = requests.get(u, headers=UA, timeout=40)
        print(f"{r.status_code} {len(r.content):>8}B {u[:140]}")
        if r.ok:
            print("   ", r.text[:900])
    except requests.RequestException as e:
        print("FAIL", u[:140], type(e).__name__)

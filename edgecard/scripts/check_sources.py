"""Smoke-test every free data source Edge Card depends on, from wherever this
runs (meant for GitHub Actions runners, since that's where the daily
pipeline runs — a source that works on a laptop but is blocked from cloud IPs
is useless to us).

Run: python scripts/check_sources.py [--samples]

Prints one line per source (OK / FAIL, HTTP status, latency, bytes) and, with
--samples, a truncated sample of each JSON payload so parsers can be written
against the real shape. Exits 0 even when sources fail: this is a report,
and the daily pipeline itself degrades per-source (see data_pipeline/freshness.py).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time

import requests

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}
NBA_STATS_HEADERS = {
    **UA,
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}

ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_CORE = "https://sports.core.api.espn.com/v2/sports"
NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download"


def _get(url: str, headers: dict | None = None, timeout: float = 20.0, stream_bytes: int | None = None):
    t0 = time.time()
    try:
        r = requests.get(url, headers=UA if headers is None else headers, timeout=timeout, stream=stream_bytes is not None)
        if stream_bytes is not None:
            body = r.raw.read(stream_bytes) if r.ok else b""
            size = int(r.headers.get("Content-Length") or len(body))
            r.close()
            return r.status_code, time.time() - t0, size, None
        return r.status_code, time.time() - t0, len(r.content), r
    except requests.RequestException as exc:
        return None, time.time() - t0, 0, exc


def _sample(obj, depth: int = 0, max_depth: int = 3):
    """Shape-preserving truncation so a sample fits in a CI log."""
    if depth >= max_depth:
        return "…" if isinstance(obj, (dict, list)) else obj
    if isinstance(obj, dict):
        return {k: _sample(v, depth + 1, max_depth) for k, v in list(obj.items())[:25]}
    if isinstance(obj, list):
        return [_sample(v, depth + 1, max_depth) for v in obj[:2]] + ([f"…(+{len(obj) - 2})"] if len(obj) > 2 else [])
    if isinstance(obj, str) and len(obj) > 120:
        return obj[:120] + "…"
    return obj


RESULTS: list[dict] = []


def check(name: str, url: str, *, headers: dict | None = None, json_sample: bool = False,
          stream_bytes: int | None = None, show: bool = False, max_depth: int = 3):
    if headers is None and "espn.com" in url:
        headers = {}  # ESPN 403s browser-like User-Agents from cloud IPs; the default one works
    status, secs, size, resp = _get(url, headers=headers, stream_bytes=stream_bytes)
    ok = status is not None and 200 <= status < 300 and (size > 0)
    err = "" if status is not None else f"{type(resp).__name__}: {str(resp)[:160]}"
    RESULTS.append({"source": name, "ok": ok, "status": status, "secs": round(secs, 2), "bytes": size, "error": err})
    print(f"[{'OK  ' if ok else 'FAIL'}] {name:<42} status={status} {secs:5.2f}s {size:>10}B {err}", flush=True)
    payload = None
    if ok and resp is not None and not isinstance(resp, Exception):
        try:
            payload = resp.json()
        except ValueError:
            payload = None
        if show:
            if payload is not None:
                print("    SAMPLE:", json.dumps(_sample(payload, max_depth=max_depth))[:6000])
            else:
                print("    SAMPLE(text):", resp.text[:1500].replace("\n", " "))
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", action="store_true", help="print truncated payload samples")
    args = ap.parse_args()
    s = args.samples
    year = dt.date.today().year
    nfl_season = year if dt.date.today().month >= 8 else year - 1
    nba_season_start = year if dt.date.today().month >= 10 else year - 1

    print(f"== Edge Card source check @ {dt.datetime.utcnow().isoformat()}Z  (NFL season {nfl_season})")

    # ---------------- ESPN (odds, schedule, injuries, news) ----------------
    sb = check("espn.nfl.scoreboard", f"{ESPN_SITE}/football/nfl/scoreboard", show=s, max_depth=5)
    event_id = None
    if sb and sb.get("events"):
        event_id = sb["events"][0]["id"]
        comp = sb["events"][0]["competitions"][0]
        print("    first event odds block:", json.dumps(comp.get("odds", ""))[:2500])
    check("espn.nba.scoreboard", f"{ESPN_SITE}/basketball/nba/scoreboard", show=False)
    if event_id:
        summ = check("espn.nfl.summary", f"{ESPN_SITE}/football/nfl/summary?event={event_id}", show=False)
        if summ:
            print("    summary keys:", list(summ.keys()))
            print("    pickcenter:", json.dumps(summ.get("pickcenter", ""))[:2500])
            print("    injuries:", json.dumps(_sample(summ.get("injuries", ""), max_depth=4))[:1500])
        odds = check("espn.core.nfl.odds(all providers)",
                     f"{ESPN_CORE}/football/leagues/nfl/events/{event_id}/competitions/{event_id}/odds?limit=50",
                     show=False)
        if odds:
            items = odds.get("items", [])
            print(f"    providers ({len(items)}):",
                  [(i.get("provider", {}).get("id"), i.get("provider", {}).get("name")) for i in items])
            if items:
                print("    provider[0] full:", json.dumps(_sample(items[0], max_depth=4))[:4000])
                pid = items[0].get("provider", {}).get("id")
                props = check("espn.core.nfl.propBets",
                              f"{ESPN_CORE}/football/leagues/nfl/events/{event_id}/competitions/{event_id}/odds/{pid}/propBets?limit=1000",
                              show=True, max_depth=5)
                if props:
                    print("    propBets count:", props.get("count"))
        check("espn.core.nfl.probabilities",
              f"{ESPN_CORE}/football/leagues/nfl/events/{event_id}/competitions/{event_id}/probabilities?limit=1",
              show=False)
    check("espn.nfl.injuries(league)", f"{ESPN_SITE}/football/nfl/injuries", show=s, max_depth=4)
    check("espn.nba.injuries(league)", f"{ESPN_SITE}/basketball/nba/injuries", show=False)
    check("espn.nfl.news", f"{ESPN_SITE}/football/nfl/news?limit=5", show=s)
    check("espn.nfl.teams", f"{ESPN_SITE}/football/nfl/teams", show=False)
    check("espn.nfl.athlete.gamelog", "https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/3139477/gamelog",
          show=False)

    # ---------------- nflverse (history, pbp, snaps, injuries, depth, NGS) ----------------
    check("nflverse.games.csv", "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv", show=False)
    for tag, fname in [
        ("pbp", f"play_by_play_{nfl_season}.parquet"),
        ("snap_counts", f"snap_counts_{nfl_season}.parquet"),
        ("injuries", f"injuries_{nfl_season}.parquet"),
        ("depth_charts", f"depth_charts_{nfl_season}.parquet"),
        ("player_stats", f"player_stats_{nfl_season}.parquet"),
        ("stats_player", f"stats_player_week_{nfl_season}.parquet"),
        ("nextgen_stats", "ngs_passing.parquet"),
        ("nextgen_stats", "ngs_receiving.parquet"),
        ("pbp", f"play_by_play_{nfl_season - 1}.parquet"),
        ("injuries", f"injuries_{nfl_season - 1}.parquet"),
    ]:
        check(f"nflverse.{tag}/{fname}", f"{NFLVERSE}/{tag}/{fname}", stream_bytes=2048)

    # ---------------- NBA ----------------
    check("nba.stats(nba_api host).leaguegamefinder",
          "https://stats.nba.com/stats/leaguegamefinder?LeagueID=00&PlayerOrTeam=T&Season=2024-25&SeasonType=Regular%20Season",
          headers=NBA_STATS_HEADERS)
    try:
        from nba_api.stats.endpoints import leaguegamefinder  # noqa: F401
        t0 = time.time()
        from nba_api.stats.endpoints import leaguegamefinder as lgf
        df = lgf.LeagueGameFinder(league_id_nullable="00", season_nullable="2024-25", timeout=30).get_data_frames()[0]
        print(f"[OK  ] nba_api.LeagueGameFinder (library)             rows={len(df)} {time.time() - t0:.1f}s")
        RESULTS.append({"source": "nba_api.library", "ok": True})
    except ImportError:
        print("[SKIP] nba_api library not installed in this env")
    except Exception as exc:  # noqa: BLE001 — report any failure mode
        print(f"[FAIL] nba_api.LeagueGameFinder (library)             {type(exc).__name__}: {str(exc)[:200]}")
        RESULTS.append({"source": "nba_api.library", "ok": False, "error": str(exc)[:200]})
    check("nba.cdn.schedule", "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json", show=False)
    check("nba.cdn.todaysScoreboard", "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json")
    check("nba.cdn.boxscore(sample game)", "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_0022400001.json")
    check("nba.cdn.playbyplay(sample game)", "https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_0022400001.json")
    check("nba.official.injury_report_index", f"https://official.nba.com/nba-injury-report-{nba_season_start}-{str(nba_season_start + 1)[2:]}-season/")
    check("nba.official.injury_report_pdf(sample)",
          "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2025-04-10_05PM.pdf", stream_bytes=1024)
    check("bbref(nba historical)", "https://www.basketball-reference.com/leagues/NBA_2025_games.html", stream_bytes=1024)

    # ---------------- NFL official injury/practice report ----------------
    check("nfl.com.injuries(page)", "https://www.nfl.com/injuries/", stream_bytes=4096)

    # ---------------- Weather ----------------
    check("open-meteo.forecast",
          "https://api.open-meteo.com/v1/forecast?latitude=42.0909&longitude=-71.2643&hourly=temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m&wind_speed_unit=mph&temperature_unit=fahrenheit&forecast_days=7",
          show=False)
    check("open-meteo.archive",
          "https://archive-api.open-meteo.com/v1/archive?latitude=42.0909&longitude=-71.2643&start_date=2024-12-01&end_date=2024-12-02&hourly=wind_speed_10m",
          show=False)

    # ---------------- News RSS ----------------
    check("rss.google_news", "https://news.google.com/rss/search?q=%22Patrick+Mahomes%22+when:2d&hl=en-US&gl=US&ceid=US:en")
    check("rss.espn_nfl", "https://www.espn.com/espn/rss/nfl/news")
    check("rss.espn_nba", "https://www.espn.com/espn/rss/nba/news")
    check("rss.cbs_nfl", "https://www.cbssports.com/rss/headlines/nfl/")
    check("rss.pft", "https://profootballtalk.nbcsports.com/feed/")
    check("rss.reddit_nfl", "https://www.reddit.com/r/nfl/new/.rss")

    # ---------------- Free historical odds candidates (NBA) ----------------
    check("hist.odds.sbro_archive", "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba-odds-2021-22/", stream_bytes=1024)

    ok = sum(1 for r in RESULTS if r.get("ok"))
    print(f"== {ok}/{len(RESULTS)} sources reachable")
    with open("source_check.json", "w") as f:
        json.dump(RESULTS, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())

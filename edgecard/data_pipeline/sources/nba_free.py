"""NBA history from free sources that work from GitHub's runners.

nba_api / stats.nba.com and cdn.nba.com are blocked from cloud IPs (both
verified from GitHub Actions: read timeout and HTTP 403). Replacements:

  ESPN scoreboard (site.api.espn.com, one request per month-range):
      schedule, final scores, neutral site, and the lines ESPN shows for
      each game (spread / total / moneylines — close-to-closing numbers).
  pbpstats.com team game logs (one request per team per season):
      possessions, points for/against -> offensive/defensive rating, pace.

What this does NOT give (and nba_api would): player tracking, lineup-level
on/off splits at scale. The cohesion / role-conflict hypotheses are therefore
not tested for the NBA yet; see README "What is and isn't tested".
"""
from __future__ import annotations

import datetime as dt
import time

import numpy as np
import pandas as pd
import requests

from data_pipeline.venues import canonical_team
from edgecard.odds import _american, _num

ESPN = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
PBP = "https://api.pbpstats.com"
PBP_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def _espn_day(day: dt.date) -> list[dict]:
    """ESPN rejects date ranges (HTTP 400), so history is fetched one day at a time."""
    url = f"{ESPN}?dates={day:%Y%m%d}"
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=30)
            if r.ok:
                return r.json().get("events", [])
        except requests.RequestException:
            pass
        time.sleep(2 ** attempt)
    return []


def _season_days(season_start: int) -> list[dt.date]:
    start, end = dt.date(season_start, 10, 1), min(dt.date(season_start + 1, 6, 30), dt.date.today() - dt.timedelta(days=1))
    return [start + dt.timedelta(days=i) for i in range((end - start).days + 1)] if end >= start else []


def espn_season_games(season_start: int) -> pd.DataFrame:
    rows = []
    for day in _season_days(season_start):
        for e in _espn_day(day):
            comp = e["competitions"][0]
            stype = (e.get("season") or {}).get("type")
            if stype not in (2, 3):  # regular season, playoffs (skip preseason / all-star)
                continue
            if comp.get("status", {}).get("type", {}).get("state") != "post":
                continue
            t = {c["homeAway"]: c for c in comp["competitors"]}
            try:
                hs, as_ = float(t["home"]["score"]), float(t["away"]["score"])
            except (KeyError, TypeError, ValueError):
                continue
            h = canonical_team("NBA", t["home"]["team"]["abbreviation"])
            a = canonical_team("NBA", t["away"]["team"]["abbreviation"])
            o = (comp.get("odds") or [{}])[0]
            spread = _num(o.get("spread"))
            ho, ao = o.get("homeTeamOdds") or {}, o.get("awayTeamOdds") or {}
            # ESPN's scoreboard 'spread' is the home line; verify sign with the favourite flag
            if spread is not None and ho.get("favorite") is True and spread > 0:
                spread = -spread
            if spread is not None and ao.get("favorite") is True and spread < 0:
                spread = -spread
            ko = pd.Timestamp(e["date"])
            rows.append({
                "game_id": e["id"], "season": season_start, "game_type": "REG" if stype == 2 else "POST",
                "kickoff": ko, "game_date": ko.tz_convert("America/New_York").strftime("%Y-%m-%d"),
                "home_team": h, "away_team": a, "home_score": hs, "away_score": as_,
                "neutral_site": int(bool(comp.get("neutralSite"))),
                "home_spread": spread, "total_line": _num(o.get("overUnder")),
                "home_moneyline": _american(ho.get("moneyLine")), "away_moneyline": _american(ao.get("moneyLine")),
                "home_spread_odds": _american(ho.get("spreadOdds")) or -110.0, "away_spread_odds": _american(ao.get("spreadOdds")) or -110.0,
                "over_odds": _american(o.get("overOdds")) or -110.0, "under_odds": _american(o.get("underOdds")) or -110.0,
                "odds_provider": (o.get("provider") or {}).get("name"),
                "overtime": int(len((t["home"].get("linescores") or [])) > 4),
            })
        time.sleep(0.25)
    df = pd.DataFrame(rows).drop_duplicates("game_id")
    return df.sort_values("kickoff").reset_index(drop=True)


def _pbp_teams() -> dict[str, str]:
    r = requests.get(f"{PBP}/get-teams/nba", headers=PBP_UA, timeout=40)
    r.raise_for_status()
    return {str(t["id"]): canonical_team("NBA", t["text"]) for t in r.json().get("teams", [])}


def pbpstats_team_games(season_start: int) -> pd.DataFrame:
    season = f"{season_start}-{str(season_start + 1)[2:]}"
    teams = _pbp_teams()
    rows = []
    for tid, abbr in teams.items():
        for stype in ("Regular Season", "Playoffs"):
            url = (f"{PBP}/get-game-logs/nba?Season={season}&SeasonType={stype.replace(' ', '%2B')}"
                   f"&EntityType=Team&EntityId={tid}")
            try:
                r = requests.get(url, headers=PBP_UA, timeout=60)
                if not r.ok:
                    continue
                for g in r.json().get("multi_row_table_data", []):
                    rows.append({"pbp_game_id": g.get("GameId"), "date": g.get("Date"), "team": abbr,
                                 "off_poss": g.get("OffPoss"), "def_poss": g.get("DefPoss"), "points": g.get("Points"),
                                 "opp_points": g.get("OpponentPoints"), "fg3a": g.get("FG3A"), "fg2a": g.get("FG2A"),
                                 "fta": g.get("FTA"), "tov": g.get("Turnovers"), "oreb": g.get("OffRebounds") or g.get("OffensiveRebounds"),
                                 "seconds": g.get("SecondsPlayed"), "season": season_start})
            except (requests.RequestException, ValueError):
                continue
            time.sleep(0.5)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["ortg"] = 100 * df["points"] / df["off_poss"].replace(0, np.nan)
    df["drtg"] = 100 * df["opp_points"] / df["def_poss"].replace(0, np.nan)
    df["pace"] = 48 * 60 * (df["off_poss"] + df["def_poss"]) / 2 / (df["seconds"].replace(0, np.nan) / 5)
    return df


def build_history(seasons: list[int]) -> dict[str, int]:
    """Incremental: a finished season that is already stored is reused, never
    re-fetched; the current season is always refreshed."""
    from edgecard.store import history_path

    gp, tp = history_path("nba_games"), history_path("nba_team_games")
    old_g = pd.read_parquet(gp) if gp.exists() else pd.DataFrame(columns=["season"])
    old_t = pd.read_parquet(tp) if tp.exists() else pd.DataFrame(columns=["season"])
    today = dt.date.today()
    current = today.year if today.month >= 10 else today.year - 1
    games, tgs = [], []
    for s in seasons:
        finished = s < current
        have_g = old_g[old_g["season"] == s]
        have_t = old_t[old_t["season"] == s]
        if finished and len(have_g) > 1000:
            games.append(have_g)
        else:
            try:
                g = espn_season_games(s)
                if len(have_g) and "home_spread" in have_g:
                    keep = have_g.set_index("game_id")[["home_spread", "total_line", "home_moneyline", "away_moneyline",
                                                        "home_spread_odds", "away_spread_odds", "over_odds", "under_odds"]]
                    g = g.set_index("game_id")
                    g.update(keep, overwrite=False)
                    g = g.reset_index()
                games.append(g)
                print(f"  NBA {s}-{s + 1}: {len(g)} games from ESPN ({g['home_spread'].notna().mean():.0%} with lines)")
            except Exception as exc:  # noqa: BLE001
                print(f"  NBA {s} ESPN FAILED: {exc}")
                games.append(have_g)
        if finished and len(have_t) > 2000:
            tgs.append(have_t)
        else:
            try:
                t = pbpstats_team_games(s)
                tgs.append(t if len(t) else have_t)
                print(f"  NBA {s}-{s + 1}: {len(t)} team-games from pbpstats")
            except Exception as exc:  # noqa: BLE001
                print(f"  NBA {s} pbpstats FAILED: {exc}")
                tgs.append(have_t)
    out = {}
    g = pd.concat([x for x in games if len(x)], ignore_index=True) if any(len(x) for x in games) else pd.DataFrame()
    if len(g):
        g.to_parquet(gp, index=False)
        out["nba_games"] = len(g)
    t = pd.concat([x for x in tgs if len(x)], ignore_index=True) if any(len(x) for x in tgs) else pd.DataFrame()
    if len(t):
        t.to_parquet(tp, index=False)
        out["nba_team_games"] = len(t)
    if len(g):
        # keep lines already backfilled for finished seasons, then fill more
        out["nba_lines_backfilled"] = backfill_lines()
    return out


CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events"
PROVIDER_PRIORITY = ("draft", "espn bet", "caesars", "fanduel", "mgm", "bet365", "consensus")


def _core_lines(event_id: str) -> dict | None:
    """Pre-game lines for one past game from ESPN's per-event odds endpoint
    (the scoreboard drops them after the game). Uses the 'close' block when
    ESPN has one, else the provider's final pre-game numbers."""
    try:
        r = requests.get(f"{CORE}/{event_id}/competitions/{event_id}/odds?limit=50", timeout=20)
        if not r.ok:
            return None
        items = [i for i in r.json().get("items", []) if "live" not in (i.get("provider", {}).get("name", "").lower())]
    except (requests.RequestException, ValueError):
        return None
    if not items:
        return None
    items.sort(key=lambda i: next((k for k, p in enumerate(PROVIDER_PRIORITY) if p in i.get("provider", {}).get("name", "").lower()), 99))
    it = items[0]
    ho, ao = it.get("homeTeamOdds") or {}, it.get("awayTeamOdds") or {}
    hc, ac = ho.get("close") or {}, ao.get("close") or {}
    spread = _num(hc.get("pointSpread")) if hc.get("pointSpread") else _num(it.get("spread"))
    if spread is not None and not hc.get("pointSpread"):
        if ho.get("favorite") is True and spread > 0:
            spread = -spread
        if ao.get("favorite") is True and spread < 0:
            spread = -spread
    tc = it.get("close") or {}
    total = _num((tc.get("total") or {}).get("alternateDisplayValue")) if isinstance(tc.get("total"), dict) else None
    return {"home_spread": spread, "total_line": abs(total) if total else _num(it.get("overUnder")),
            "home_moneyline": _american(hc.get("moneyLine")) or _american(ho.get("moneyLine")),
            "away_moneyline": _american(ac.get("moneyLine")) or _american(ao.get("moneyLine")),
            "home_spread_odds": _american(hc.get("spread")) or _american(ho.get("spreadOdds")) or -110.0,
            "away_spread_odds": _american(ac.get("spread")) or _american(ao.get("spreadOdds")) or -110.0,
            "over_odds": _american((tc.get("over") or {})) or _american(it.get("overOdds")) or -110.0,
            "under_odds": _american((tc.get("under") or {})) or _american(it.get("underOdds")) or -110.0,
            "odds_provider": it.get("provider", {}).get("name")}


def backfill_lines(max_requests: int = 9000) -> int:
    """Fills missing lines newest-first, capped per run (one request per
    game), so the weekly job completes the history over a few runs."""
    from edgecard.store import history_path

    gp = history_path("nba_games")
    if not gp.exists():
        return 0
    g = pd.read_parquet(gp)
    for c in ("home_spread", "total_line", "home_moneyline", "away_moneyline", "home_spread_odds", "away_spread_odds",
              "over_odds", "under_odds", "odds_provider"):
        if c not in g:
            g[c] = np.nan
    g["odds_provider"] = g["odds_provider"].astype(object)
    todo = g[g["home_spread"].isna() & g["total_line"].isna()].sort_values("kickoff", ascending=False).head(max_requests)
    n = 0
    for idx, r in todo.iterrows():
        lines = _core_lines(str(r["game_id"]))
        time.sleep(0.2)
        if lines:
            for k, v in lines.items():
                g.at[idx, k] = v
            n += 1
    g.to_parquet(gp, index=False)
    print(f"  NBA lines backfilled for {n}/{len(todo)} games; {int((g['home_spread'].isna()).sum())} still missing")
    return n

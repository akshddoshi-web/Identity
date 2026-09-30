"""Odds ingestion from free sources, normalized to one long table.

Sources (all free, no key; verified reachable from GitHub runners by
scripts/check_sources*.py):
  - ESPN core API: every provider ESPN lists for the event (DraftKings, and
    for many NBA games Caesars/Betfair/etc.), with ESPN's own open / close
    / current values. Also DraftKings player-prop LINES (no prices).
  - Action Network public scoreboard: current prices at several books, plus
    their "Open" pseudo-book (opening line).
  - Kalshi public markets: exchange prices on game winners, converted to an
    American price AFTER Kalshi's trading fee.

Row schema (one row per side):
  league, game_key, espn_id, commence_time, home_team, away_team,
  source, book, market (moneyline|spread|total), side (home|away|over|under),
  point (spread from this side's perspective, or the total), price (American),
  line_type (current|open|close), captured_at, tag (live|close)

ESPN rejects browser-looking User-Agents from cloud IPs (403) but accepts
the default python-requests one, so no UA spoofing is done anywhere here.
Requests are few (one per game per source per run) and spaced out.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import time
from dataclasses import dataclass

import pandas as pd
import requests

from data_pipeline.venues import canonical_team
from edgecard import store
from edgecard.freshness import record

ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_CORE = "https://sports.core.api.espn.com/v2/sports"
AN_BASE = "https://api.actionnetwork.com/web/v1"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"

SPORT_PATH = {"NFL": ("football", "nfl"), "NBA": ("basketball", "nba")}
KALSHI_SERIES = {"NFL": "KXNFLGAME", "NBA": "KXNBAGAME"}
AN_BOOK_IDS = "15,30,68,69,71,75,79,123,247,280,972,1005,1006"
PAUSE = 0.35

_session = requests.Session()


def _get(url: str, **kw) -> dict | None:
    try:
        r = _session.get(url, timeout=20, **kw)
        if r.ok:
            return r.json()
    except (requests.RequestException, ValueError):
        return None
    return None


def game_key(league: str, commence_time: str, away: str, home: str) -> str:
    """Stable id shared by every source: league_YYYYMMDD_AWAY_HOME (ET date)."""
    t = pd.Timestamp(commence_time)
    t = t.tz_localize("UTC") if t.tzinfo is None else t
    d = t.tz_convert("America/New_York").strftime("%Y%m%d")
    return f"{league}_{d}_{away}_{home}"


# --------------------------------------------------------------------------- #
# Schedule (ESPN scoreboard)
# --------------------------------------------------------------------------- #

@dataclass
class Event:
    league: str
    espn_id: str
    game_key: str
    commence_time: str
    home_team: str
    away_team: str
    home_espn_id: str
    away_espn_id: str
    status: str            # pre | in | post
    neutral: bool
    home_score: float | None = None
    away_score: float | None = None
    venue: str | None = None
    week: int | None = None
    leaders: str = "[]"   # JSON [[player, team], ...] from ESPN's per-team stat leaders


def fetch_events(league: str, days_ahead: int = 2, dates: list[str] | None = None) -> list[Event]:
    sport, lg = SPORT_PATH[league]
    urls = []
    if dates:
        urls = [f"{ESPN_SITE}/{sport}/{lg}/scoreboard?dates={d}" for d in dates]
    elif league == "NFL":
        # the default NFL scoreboard keeps showing the finished week until
        # Tuesday, and ESPN rejects date ranges (HTTP 400), so ask day by day
        # for the next 7 days (one request per day)
        today = dt.datetime.now(dt.timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date()
        urls = [f"{ESPN_SITE}/{sport}/{lg}/scoreboard?dates={(today + dt.timedelta(days=i)).strftime('%Y%m%d')}"
                for i in range(8)]
    else:
        today = dt.datetime.now(dt.timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date()
        urls = [f"{ESPN_SITE}/{sport}/{lg}/scoreboard?dates={(today + dt.timedelta(days=i)).strftime('%Y%m%d')}"
                for i in range(days_ahead + 1)]
    events: dict[str, Event] = {}
    for u in urls:
        data = _get(u)
        time.sleep(PAUSE)
        if not data:
            continue
        for e in data.get("events", []):
            comp = e["competitions"][0]
            teams = {c["homeAway"]: c for c in comp["competitors"]}
            if "home" not in teams or "away" not in teams:
                continue
            h = canonical_team(league, teams["home"]["team"]["abbreviation"])
            a = canonical_team(league, teams["away"]["team"]["abbreviation"])
            status = comp.get("status", e.get("status", {})).get("type", {}).get("state", "pre")

            def _score(c):
                try:
                    return float(c.get("score")) if status != "pre" else None
                except (TypeError, ValueError):
                    return None

            leaders = []
            for side in ("home", "away"):
                ab = canonical_team(league, teams[side]["team"]["abbreviation"])
                for cat in teams[side].get("leaders", []) or []:
                    for ld in (cat.get("leaders") or [])[:1]:
                        nm = (ld.get("athlete") or {}).get("displayName")
                        if nm and [nm, ab] not in leaders:
                            leaders.append([nm, ab])
            events[e["id"]] = Event(
                league=league, espn_id=e["id"], game_key=game_key(league, e["date"], a, h),
                commence_time=e["date"], home_team=h, away_team=a,
                home_espn_id=teams["home"]["team"]["id"], away_espn_id=teams["away"]["team"]["id"],
                status=status, neutral=bool(comp.get("neutralSite")),
                home_score=_score(teams["home"]), away_score=_score(teams["away"]),
                venue=(comp.get("venue") or {}).get("fullName"),
                week=(e.get("week") or {}).get("number"), leaders=__import__("json").dumps(leaders),
            )
    return list(events.values())


# --------------------------------------------------------------------------- #
# ESPN odds (all providers ESPN carries)
# --------------------------------------------------------------------------- #

def _american(x) -> float | None:
    if x is None:
        return None
    if isinstance(x, dict):
        x = x.get("american") or x.get("alternateDisplayValue")
    try:
        s = str(x).replace("+", "").strip()
        if s.upper() in ("EVEN", "EV"):
            return 100.0
        v = float(s)
        return v if abs(v) >= 100 else None
    except (TypeError, ValueError):
        return None


def _num(x) -> float | None:
    if x is None:
        return None
    if isinstance(x, dict):
        x = x.get("value", x.get("american"))
    try:
        return float(str(x).replace("+", ""))
    except (TypeError, ValueError):
        return None


def _book_name(provider_name: str) -> str | None:
    n = provider_name.lower()
    if "live" in n:  # in-game lines are not pre-game prices
        return None
    for key, canon in (("draft", "draftkings"), ("fanduel", "fanduel"), ("caesars", "caesars"), ("caesar", "caesars"),
                       ("mgm", "betmgm"), ("betfair", "betfair"), ("bet 365", "bet365"), ("bet365", "bet365"),
                       ("espn bet", "espnbet"), ("unibet", "unibet"), ("westgate", "westgate"), ("wynn", "wynn"),
                       ("consensus", "consensus"), ("numberfire", None), ("teamrankings", None)):
        if key in n:
            return canon
    return re.sub(r"[^a-z0-9]+", "", n) or None


def parse_espn_odds_item(ev: Event, item: dict, captured_at: str, tag: str) -> list[dict]:
    book = _book_name(item.get("provider", {}).get("name", ""))
    if not book:
        return []
    base = dict(league=ev.league, game_key=ev.game_key, espn_id=ev.espn_id, commence_time=ev.commence_time,
                home_team=ev.home_team, away_team=ev.away_team, source="espn", book=book,
                captured_at=captured_at, tag=tag)
    rows: list[dict] = []
    ho, ao = item.get("homeTeamOdds") or {}, item.get("awayTeamOdds") or {}

    # current values sit at the top level
    home_ml, away_ml = _american(ho.get("moneyLine")), _american(ao.get("moneyLine"))
    spread = _num(item.get("spread"))  # ESPN: home spread (negative = home favoured)
    if home_ml and away_ml:
        rows += [dict(base, market="moneyline", side="home", point=None, price=home_ml, line_type="current"),
                 dict(base, market="moneyline", side="away", point=None, price=away_ml, line_type="current")]
    hs, as_ = _american(ho.get("spreadOdds")), _american(ao.get("spreadOdds"))
    if spread is not None and hs and as_:
        # item["spread"] is the HOME line in ESPN's feed; sanity-check with favourite flag
        home_pt = spread
        if ho.get("favorite") is True and home_pt > 0:
            home_pt = -home_pt
        if ao.get("favorite") is True and home_pt < 0:
            home_pt = -home_pt
        rows += [dict(base, market="spread", side="home", point=home_pt, price=hs, line_type="current"),
                 dict(base, market="spread", side="away", point=-home_pt, price=as_, line_type="current")]
    ou, over, under = _num(item.get("overUnder")), _american(item.get("overOdds")), _american(item.get("underOdds"))
    if ou and over and under:
        rows += [dict(base, market="total", side="over", point=ou, price=over, line_type="current"),
                 dict(base, market="total", side="under", point=ou, price=under, line_type="current")]

    # open / close blocks, where ESPN carries them
    for lt in ("open", "close"):
        hb, ab = ho.get(lt) or {}, ao.get(lt) or {}
        hml, aml = _american(hb.get("moneyLine")), _american(ab.get("moneyLine"))
        if hml and aml:
            rows += [dict(base, market="moneyline", side="home", point=None, price=hml, line_type=lt),
                     dict(base, market="moneyline", side="away", point=None, price=aml, line_type=lt)]
        hp, ap = _num(hb.get("pointSpread")), _num(ab.get("pointSpread"))
        hsp, asp = _american(hb.get("spread")), _american(ab.get("spread"))
        if hp is not None and hsp and asp:
            rows += [dict(base, market="spread", side="home", point=hp, price=hsp, line_type=lt),
                     dict(base, market="spread", side="away", point=ap if ap is not None else -hp, price=asp, line_type=lt)]
        tb = (item.get(lt) or {})
        tot = _num((tb.get("total") or {}).get("alternateDisplayValue") if isinstance(tb.get("total"), dict) else tb.get("total"))
        o_, u_ = _american((tb.get("over") or {})), _american((tb.get("under") or {}))
        if tot and o_ and u_:
            rows += [dict(base, market="total", side="over", point=abs(tot), price=o_, line_type=lt),
                     dict(base, market="total", side="under", point=abs(tot), price=u_, line_type=lt)]
    return rows


def fetch_espn_odds(ev: Event, captured_at: str, tag: str) -> list[dict]:
    sport, lg = SPORT_PATH[ev.league]
    data = _get(f"{ESPN_CORE}/{sport}/leagues/{lg}/events/{ev.espn_id}/competitions/{ev.espn_id}/odds?limit=100")
    time.sleep(PAUSE)
    rows: list[dict] = []
    for it in (data or {}).get("items", []):
        rows += parse_espn_odds_item(ev, it, captured_at, tag)
    return rows


# --------------------------------------------------------------------------- #
# ESPN player props (DraftKings lines; prices are NOT published)
# --------------------------------------------------------------------------- #

PROP_TYPES = {
    "Total Passing Yards": "pass_yds", "Total Pass Completions": "pass_cmp", "Total Passing Attempts": "pass_att",
    "Total Passing Touchdowns": "pass_td", "Total Passing Interceptions": "pass_int", "Total Carries": "rush_att",
    "Total Rushing Yards": "rush_yds", "Total Receiving Yards": "rec_yds", "Total Receptions": "receptions",
    "Total Rushing Plus Receiving Yards": "rush_rec_yds", "Total Passing Plus Rushing Yards": "pass_rush_yds",
    "Anytime Touchdown Scorer": "anytime_td",
    # NBA
    "Total Points": "pts", "Total Rebounds": "reb", "Total Assists": "ast", "Total Three Pointers Made": "fg3m",
    "Total Points, Rebounds, and Assists": "pra", "Total Points and Rebounds": "pr", "Total Points and Assists": "pa",
    "Total Rebounds and Assists": "ra", "Total Steals": "stl", "Total Blocks": "blk",
}


def _prop_market(type_name: str) -> str | None:
    base = type_name.split(" (")[0].strip()
    if "1st" in base or "Quarter" in base or "Half" in base or "Milestone" in base:
        return None
    return PROP_TYPES.get(base)


def fetch_roster_names(league: str, team_espn_id: str) -> dict[str, tuple[str, str]]:
    sport, lg = SPORT_PATH[league]
    data = _get(f"{ESPN_SITE}/{sport}/{lg}/teams/{team_espn_id}/roster")
    time.sleep(PAUSE)
    out: dict[str, tuple[str, str]] = {}
    if not data:
        return out
    groups = data.get("athletes", [])
    items = []
    for g in groups:
        items += g.get("items", []) if isinstance(g, dict) and "items" in g else [g]
    for a in items:
        if isinstance(a, dict) and a.get("id"):
            out[str(a["id"])] = (a.get("displayName") or a.get("fullName") or "", (a.get("position") or {}).get("abbreviation", ""))
    return out


def fetch_espn_props(ev: Event, captured_at: str, tag: str, provider_id: str = "100") -> list[dict]:
    sport, lg = SPORT_PATH[ev.league]
    data = _get(f"{ESPN_CORE}/{sport}/leagues/{lg}/events/{ev.espn_id}/competitions/{ev.espn_id}/odds/{provider_id}/propBets?limit=1000")
    time.sleep(PAUSE)
    if not data:
        return []
    names = {}
    for tid, team in ((ev.home_espn_id, ev.home_team), (ev.away_espn_id, ev.away_team)):
        for aid, (nm, pos) in fetch_roster_names(ev.league, tid).items():
            names[aid] = (nm, pos, team)
    seen, rows = set(), []
    for it in data.get("items", []):
        market = _prop_market(it.get("type", {}).get("name", ""))
        ath = (it.get("athlete") or {}).get("$ref", "")
        m = re.search(r"/athletes/(\d+)", ath)
        if not market or not m:
            continue
        aid = m.group(1)
        line = _num((it.get("current") or {}).get("target"))
        open_line = _num((it.get("open") or {}).get("target"))
        if market != "anytime_td" and line is None:
            continue
        key = (aid, market, line)
        if key in seen:  # feed lists over and under as two identical entries
            continue
        seen.add(key)
        nm, pos, team = names.get(aid, ("", "", None))
        rows.append(dict(league=ev.league, game_key=ev.game_key, espn_id=ev.espn_id, commence_time=ev.commence_time,
                         home_team=ev.home_team, away_team=ev.away_team, athlete_id=aid, player=nm, position=pos,
                         team=team, market=market, line=line, open_line=open_line, book="draftkings",
                         price_over=None, price_under=None, price_source="assumed_-110",
                         captured_at=captured_at, tag=tag, last_updated=it.get("lastUpdated")))
    return rows


# --------------------------------------------------------------------------- #
# Action Network (multi-book current prices + opening line)
# --------------------------------------------------------------------------- #

_AN_BOOKS: dict[int, str] | None = None


def _an_books() -> dict[int, str]:
    global _AN_BOOKS
    if _AN_BOOKS is None:
        data = _get(f"{AN_BASE}/books") or {}
        _AN_BOOKS = {}
        for b in data.get("books", []):
            nm = (b.get("display_name") or "").lower()
            canon = _book_name(nm) or nm
            if b.get("id") == 30:
                canon = "open"
            elif b.get("id") == 15:
                canon = "consensus"
            _AN_BOOKS[int(b["id"])] = canon
    return _AN_BOOKS


def fetch_action_network(league: str, events: list[Event], captured_at: str, tag: str) -> list[dict]:
    lg = league.lower()
    # the default scoreboard is the *current* (often finished) week: ask per event date
    days = sorted({pd.Timestamp(e.commence_time).tz_convert("America/New_York").strftime("%Y%m%d") for e in events})
    games = []
    for d in days:
        data = _get(f"{AN_BASE}/scoreboard/{lg}?period=game&bookIds={AN_BOOK_IDS}&date={d}")
        time.sleep(PAUSE)
        if data:
            games += data.get("games", [])
    if not games:
        return []
    data = {"games": games}
    books = _an_books()
    by_teams = {(e.home_team, e.away_team): e for e in events}
    rows = []
    for g in data.get("games", []):
        teams = {t["id"]: canonical_team(league, t.get("abbr", "")) for t in g.get("teams", [])}
        h, a = teams.get(g.get("home_team_id")), teams.get(g.get("away_team_id"))
        ev = by_teams.get((h, a))
        # Action Network ignores the date parameter and keeps serving the
        # finished week until it rolls over; only accept the same game
        try:
            if ev is None or abs(pd.Timestamp(g["start_time"]) - pd.Timestamp(ev.commence_time)) > pd.Timedelta(hours=24):
                continue
        except (KeyError, ValueError, TypeError):
            continue
        for o in g.get("odds", []):
            if o.get("type") != "game":
                continue
            bid = int(o.get("book_id", 0))
            book = books.get(bid, f"an{bid}")
            lt = "open" if book == "open" else "current"
            if book == "open":
                book = "market_open"
            base = dict(league=league, game_key=ev.game_key, espn_id=ev.espn_id, commence_time=ev.commence_time,
                        home_team=ev.home_team, away_team=ev.away_team, source="actionnetwork", book=book,
                        captured_at=captured_at, tag=tag, line_type=lt)
            if o.get("ml_home") and o.get("ml_away"):
                rows += [dict(base, market="moneyline", side="home", point=None, price=float(o["ml_home"])),
                         dict(base, market="moneyline", side="away", point=None, price=float(o["ml_away"]))]
            if o.get("spread_home") is not None and o.get("spread_home_line") and o.get("spread_away_line"):
                rows += [dict(base, market="spread", side="home", point=float(o["spread_home"]), price=float(o["spread_home_line"])),
                         dict(base, market="spread", side="away", point=float(o["spread_away"]), price=float(o["spread_away_line"]))]
            if o.get("total") and o.get("over") and o.get("under"):
                rows += [dict(base, market="total", side="over", point=float(o["total"]), price=float(o["over"])),
                         dict(base, market="total", side="under", point=float(o["total"]), price=float(o["under"]))]
    return rows


# --------------------------------------------------------------------------- #
# Kalshi (exchange; fee-adjusted)
# --------------------------------------------------------------------------- #

def kalshi_fee_adjusted_american(yes_ask: float) -> float | None:
    """Kalshi charges ~0.07 * P * (1-P) per $1 contract on taker fills.
    Effective cost per $1 payout = ask + fee; convert to an American price."""
    if not (0.01 <= yes_ask <= 0.99):
        return None
    cost = yes_ask + math.ceil(0.07 * yes_ask * (1 - yes_ask) * 100) / 100
    if cost >= 1:
        return None
    dec = 1.0 / cost
    return round((dec - 1) * 100, 1) if dec >= 2 else round(-100 / (dec - 1), 1)


def fetch_kalshi(league: str, events: list[Event], captured_at: str, tag: str) -> list[dict]:
    data = _get(f"{KALSHI}/markets?limit=1000&status=open&series_ticker={KALSHI_SERIES[league]}")
    if not data:
        return []
    rows = []
    idx = {}
    for e in events:
        d = pd.Timestamp(e.commence_time).tz_convert("America/New_York").strftime("%y%b%d").upper()
        idx[(d, e.away_team, e.home_team)] = e
    for m in data.get("markets", []):
        tk = m.get("ticker", "")  # e.g. KXNFLGAME-26OCT05ATLNO-NO
        mm = re.match(r".*-(\d{2}[A-Z]{3}\d{2})([A-Z]+)-([A-Z]+)$", tk)
        if not mm:
            continue
        date, pair, winner = mm.groups()
        ev = None
        for (d, a, h), e in idx.items():
            if d == date and pair in (f"{a}{h}", f"{canonical_team(league, a)}{canonical_team(league, h)}"):
                ev = e
                break
            if d == date and pair.startswith(a[:3]) and pair.endswith(h[:3]):
                ev = e
                break
        if ev is None:
            continue
        side = "home" if canonical_team(league, winner) == ev.home_team else "away" if canonical_team(league, winner) == ev.away_team else None
        try:
            ask = float(m.get("yes_ask_dollars") or 0)
        except (TypeError, ValueError):
            continue
        price = kalshi_fee_adjusted_american(ask)
        if side and price:
            rows.append(dict(league=league, game_key=ev.game_key, espn_id=ev.espn_id, commence_time=ev.commence_time,
                             home_team=ev.home_team, away_team=ev.away_team, source="kalshi", book="kalshi",
                             market="moneyline", side=side, point=None, price=price, line_type="current",
                             captured_at=captured_at, tag=tag))
    return rows


# --------------------------------------------------------------------------- #
# Snapshot orchestration
# --------------------------------------------------------------------------- #

KEY_COLS = ["game_key", "book", "market", "side", "line_type"]


def _dedupe_against_last(new: pd.DataFrame, league: str) -> pd.DataFrame:
    """Keeps a row only if its (point, price) differs from the latest stored
    row for the same key — line history without storing identical rows
    every run. Closing captures (tag=close) are always kept."""
    if new.empty:
        return new
    hist = store.read_parquet_glob(("odds", league.lower()), since=dt.date.today() - dt.timedelta(days=10))
    if hist.empty:
        return new
    last = hist.sort_values("captured_at").groupby(KEY_COLS).tail(1)[KEY_COLS + ["point", "price"]]
    m = new.merge(last, on=KEY_COLS, how="left", suffixes=("", "_last"))
    same = (m["price"] == m["price_last"]) & ((m["point"] == m["point_last"]) | (m["point"].isna() & m["point_last"].isna()))
    keep = ~same | (m["tag"] == "close")
    return new[keep.values]


def snapshot_all(league: str, tag: str = "live") -> dict:
    captured_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    events = [e for e in fetch_events(league) if e.status == "pre"]
    record(f"{league.lower()}.espn.schedule", ok=bool(events), n=len(events), note="upcoming events")
    rows, prop_rows = [], []
    for ev in events:
        rows += fetch_espn_odds(ev, captured_at, tag)
    record(f"{league.lower()}.espn.odds", ok=bool(rows), n=len(rows))
    an = fetch_action_network(league, events, captured_at, tag)
    record(f"{league.lower()}.actionnetwork.odds", ok=bool(an), n=len(an))
    ka = fetch_kalshi(league, events, captured_at, tag)
    record(f"{league.lower()}.kalshi.moneyline", ok=bool(ka), n=len(ka))
    rows += an + ka
    # props only for games in the next ~36h (they aren't posted earlier anyway)
    soon = pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=36)
    for ev in events:
        if pd.Timestamp(ev.commence_time) <= soon:
            prop_rows += fetch_espn_props(ev, captured_at, tag)
    record(f"{league.lower()}.espn.props", ok=bool(prop_rows), n=len(prop_rows), note="DraftKings lines; prices not published")

    day = dt.date.today().isoformat()
    df = pd.DataFrame(rows)
    if not df.empty:
        df = _dedupe_against_last(df, league)
        store.append_parquet(df, "odds", league.lower(), f"{day}.parquet")
    pdf = pd.DataFrame(prop_rows)
    if not pdf.empty:
        store.append_parquet(pdf, "props", league.lower(), f"{day}.parquet")
    events_df = pd.DataFrame([e.__dict__ for e in events])
    if not events_df.empty:
        store.append_parquet(events_df.assign(captured_at=captured_at), "events", league.lower(), f"{day}.parquet")
    summary = {"league": league, "events": len(events), "odds_rows": len(df), "prop_rows": len(pdf), "captured_at": captured_at}
    from edgecard.freshness import flush

    flush()
    print(summary)
    return summary


def latest_lines(league: str, days: int = 7) -> pd.DataFrame:
    """Latest known price per (game, book, market, side, line_type)."""
    hist = store.read_parquet_glob(("odds", league.lower()), since=dt.date.today() - dt.timedelta(days=days))
    if hist.empty:
        return hist
    return hist.sort_values("captured_at").groupby(KEY_COLS).tail(1).reset_index(drop=True)


def latest_props(league: str, days: int = 2) -> pd.DataFrame:
    hist = store.read_parquet_glob(("props", league.lower()), since=dt.date.today() - dt.timedelta(days=days))
    if hist.empty:
        return hist
    return hist.sort_values("captured_at").groupby(["game_key", "athlete_id", "market"]).tail(1).reset_index(drop=True)


_TEAM_IDS: dict[str, dict[str, str]] = {}


def espn_team_abbrs(league: str) -> dict[str, str]:
    """ESPN team id -> canonical abbreviation (cached per run)."""
    if league not in _TEAM_IDS:
        sport, lg = SPORT_PATH[league]
        data = _get(f"{ESPN_SITE}/{sport}/{lg}/teams") or {}
        out = {}
        for sp in data.get("sports", []):
            for lgd in sp.get("leagues", []):
                for t in lgd.get("teams", []):
                    tm = t.get("team", {})
                    if tm.get("id") and tm.get("abbreviation"):
                        out[str(tm["id"])] = canonical_team(league, tm["abbreviation"])
        _TEAM_IDS[league] = out
    return _TEAM_IDS[league]

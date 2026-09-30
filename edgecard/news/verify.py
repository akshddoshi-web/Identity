"""News & context verification layer (free sources only, no LLM API).

Before a bet is finalized, every team and player involved is checked
against:
  - official injury designations: ESPN's league injury feed (mirrors the
    NFL/NBA official reports and practice participation), plus nflverse's
    weekly report for NFL practice participation;
  - the last 48 hours of news: Google News RSS per player/team, ESPN's
    news API, and beat-oriented RSS (ProFootballTalk, CBS);
  - line movement since open (a sharp move against our side is a flag).

Findings become structured flags:
    {player, team, flag_type, severity, source, url, timestamp, text}

Rules (enforced in apply_flags):
  - flags can LOWER a projection (usage multiplier) or VETO a bet;
  - they never raise confidence or stake;
  - an unresolved key player (questionable / game-time decision) turns
    the bet into "WAIT — recheck after <time>".

Keyword rules are deliberately conservative: a headline that mentions a
player together with an injury/illness/suspension/personal/trade term is
enough to flag it for a human look; severity decides whether it vetoes.
"""
from __future__ import annotations

import datetime as dt
import email.utils
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from urllib.parse import quote_plus

import requests

from edgecard.freshness import record

ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports"
SPORT_PATH = {"NFL": ("football", "nfl"), "NBA": ("basketball", "nba")}
RSS_FEEDS = {
    "NFL": ["https://profootballtalk.nbcsports.com/feed/", "https://www.cbssports.com/rss/headlines/nfl/"],
    "NBA": ["https://www.cbssports.com/rss/headlines/nba/"],
}
UA = {"User-Agent": "edgecard/1.0 (+https://github.com/akshddoshi-web/Identity)"}

FLAG_PATTERNS: list[tuple[str, str, int]] = [
    # (flag_type, regex, base severity 1-3)
    ("ruled_out", r"\b(ruled out|will not play|won't play|out for (the )?(game|season)|placed on (ir|injured reserve)|season-ending)\b", 3),
    ("suspension", r"\b(suspend(ed|sion)|banned)\b", 3),
    ("personal", r"\b(personal (matter|reasons)|family (matter|emergency)|bereavement|excused)\b", 2),
    ("illness", r"\b(illness|flu|sick|non-covid|stomach)\b", 2),
    ("injury", r"\b(injur(y|ed)|hamstring|ankle|knee|concussion|protocol|sprain|strain|mri|limped|carted)\b", 2),
    ("load_management", r"\b(rest(ed|ing)?|load management|maintenance|day off|minutes restriction|snap count|pitch count)\b", 2),
    ("game_time_decision", r"\b(game[- ]time decision|questionable|doubtful|limited in practice|did not practice|dnp)\b", 2),
    ("trade", r"\b(trade[ds]?|traded|dealt|trade request|shopping)\b", 1),
    ("conflict", r"\b(locker room|feud|frustrat(ed|ion)|benched|demoted|sideline (spat|argument)|holdout|hold-in)\b", 1),
    ("coaching", r"\b(fired|interim (head )?coach|play-?calling (duties|change)|new offensive coordinator)\b", 1),
    ("weather", r"\b(weather|wind|snow|storm|rain delay|lightning)\b", 1),
]

STATUS_SEVERITY = {"out": 3, "injured reserve": 3, "suspension": 3, "doubtful": 3, "questionable": 2,
                   "day-to-day": 2, "probable": 0, "active": 0}


@dataclass
class Flag:
    player: str | None
    team: str | None
    flag_type: str
    severity: int          # 0 info, 1 low, 2 adjust/wait, 3 veto
    source: str
    url: str | None
    timestamp: str
    text: str
    status: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def _get(url: str, **kw):
    try:
        r = requests.get(url, timeout=15, **kw)
        return r if r.ok else None
    except requests.RequestException:
        return None


# --------------------------------------------------------------------------- #
# official injury designations (ESPN league feed)
# --------------------------------------------------------------------------- #

def fetch_injury_designations(league: str) -> list[Flag]:
    sport, lg = SPORT_PATH[league]
    r = _get(f"{ESPN_SITE}/{sport}/{lg}/injuries")  # no custom UA (ESPN blocks browser-like UAs from cloud IPs)
    flags: list[Flag] = []
    if r is None:
        record(f"{league.lower()}.espn.injuries", ok=False)
        return flags
    from data_pipeline.venues import canonical_team

    from edgecard.odds import espn_team_abbrs

    ids = espn_team_abbrs(league)
    data = r.json()
    for team_block in data.get("injuries", []):
        team_abbr = ids.get(str(team_block.get("id")))
        for inj in team_block.get("injuries", []):
            ath = inj.get("athlete", {}) or {}
            team_abbr = team_abbr or canonical_team(league, ((ath.get("team") or {}).get("abbreviation") or ""))
            status = str(inj.get("status") or inj.get("type", {}).get("description") or "").lower()
            detail = inj.get("shortComment") or inj.get("longComment") or ""
            sev = next((v for k, v in STATUS_SEVERITY.items() if k in status), 1)
            flags.append(Flag(player=ath.get("displayName"), team=team_abbr, flag_type="official_status",
                              severity=sev, source="ESPN injury report (official designations)",
                              url=((ath.get("links") or [{}])[0] or {}).get("href"),
                              timestamp=inj.get("date") or dt.datetime.now(dt.timezone.utc).isoformat(),
                              text=f"{status}: {detail}"[:300], status=status))
    record(f"{league.lower()}.espn.injuries", ok=True, n=len(flags))
    return flags


# --------------------------------------------------------------------------- #
# news scan
# --------------------------------------------------------------------------- #

def _parse_rss(xml_text: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
        link = it.findtext("link")
        pub = it.findtext("pubDate")
        ts = None
        if pub:
            try:
                ts = email.utils.parsedate_to_datetime(pub).astimezone(dt.timezone.utc)
            except (TypeError, ValueError):
                ts = None
        items.append({"title": title, "text": f"{title}. {desc}", "url": link, "ts": ts,
                      "source": (it.findtext("source") or "").strip()})
    return items


def classify(text: str) -> list[tuple[str, int]]:
    t = text.lower()
    return [(ft, sev) for ft, rx, sev in FLAG_PATTERNS if re.search(rx, t)]


def _name_in(text: str, name: str) -> bool:
    if not name:
        return False
    parts = name.split()
    return name.lower() in text.lower() or (len(parts) > 1 and re.search(rf"\b{re.escape(parts[-1])}\b", text) is not None
                                             and parts[0][0].lower() in text.lower())


def scan_news(league: str, players: list[tuple[str, str]], teams: list[str], hours: int = 48,
              max_player_queries: int = 40) -> list[Flag]:
    """players: [(name, team)]. Google News RSS is queried per player (capped)
    and per team; league feeds are scanned once for any named player."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    flags: list[Flag] = []
    seen = set()

    def _emit(items, who: str | None, team: str | None, src: str):
        for it in items:
            if it["ts"] is not None and it["ts"] < cutoff:
                continue
            if who and not _name_in(it["text"], who):
                continue
            for ft, sev in classify(it["text"]):
                key = (who, ft, it["url"])
                if key in seen:
                    continue
                seen.add(key)
                flags.append(Flag(player=who, team=team, flag_type=ft, severity=min(sev, 2) if ft != "ruled_out" else sev,
                                  source=f"{src}{' / ' + it['source'] if it['source'] else ''}", url=it["url"],
                                  timestamp=(it["ts"] or dt.datetime.now(dt.timezone.utc)).isoformat(),
                                  text=it["title"][:240]))

    ok = 0
    for name, team in players[:max_player_queries]:
        q = quote_plus(f'"{name}" when:2d')
        r = _get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en", headers=UA)
        time.sleep(0.4)
        if r is not None:
            ok += 1
            _emit(_parse_rss(r.text), name, team, "Google News")
    for team in teams:
        q = quote_plus(f'"{team}" {league} injury OR lineup OR suspended when:2d')
        r = _get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en", headers=UA)
        time.sleep(0.4)
        if r is not None:
            ok += 1
            for it in _parse_rss(r.text):
                for name, t in players:
                    if t == team and _name_in(it["text"], name):
                        _emit([it], name, team, "Google News (team)")
    record(f"{league.lower()}.news.google_rss", ok=ok > 0, n=ok, note="per-player/team queries, last 48h")

    league_items = []
    for url in RSS_FEEDS.get(league, []):
        r = _get(url, headers=UA)
        if r is not None:
            league_items += [dict(it, source=url.split("/")[2]) for it in _parse_rss(r.text)]
    sport, lg = SPORT_PATH[league]
    r = _get(f"{ESPN_SITE}/{sport}/{lg}/news?limit=50")
    if r is not None:
        for a in r.json().get("articles", []):
            try:
                ts = dt.datetime.fromisoformat(a.get("published", "").replace("Z", "+00:00"))
            except ValueError:
                ts = None
            league_items.append({"title": a.get("headline", ""), "text": f"{a.get('headline', '')}. {a.get('description', '')}",
                                 "url": ((a.get("links") or {}).get("web") or {}).get("href"), "ts": ts, "source": "ESPN"})
    record(f"{league.lower()}.news.league_feeds", ok=bool(league_items), n=len(league_items))
    for name, team in players:
        _emit(league_items, name, team, "League news")
    return flags


# --------------------------------------------------------------------------- #
# line movement
# --------------------------------------------------------------------------- #

def line_move_flag(open_prob: float | None, now_prob: float | None, side_label: str, threshold: float = 0.03) -> Flag | None:
    """Flags a move of >= `threshold` in no-vig probability AGAINST our side
    since the open: the market may know something we don't."""
    if open_prob is None or now_prob is None:
        return None
    move = now_prob - open_prob
    if move <= -threshold:
        # a big move against us needs a human look before betting; a modest one is shown only
        sev = 2 if move <= -2 * threshold else 1
        return Flag(player=None, team=None, flag_type="line_move_against", severity=sev, source="odds history (open vs now)",
                    url=None, timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
                    text=f"{side_label}: no-vig probability moved {move:+.1%} since open ({open_prob:.1%} -> {now_prob:.1%})")
    return None


# --------------------------------------------------------------------------- #
# applying flags
# --------------------------------------------------------------------------- #

def usage_status(flags: list[Flag], player: str) -> str | None:
    """Maps a player's flags onto the projection status vocabulary
    (out/doubtful/questionable). Returns None if nothing applies."""
    worst = None
    order = {"out": 3, "doubtful": 2, "questionable": 1}
    for f in flags:
        if f.player != player:
            continue
        st = None
        if f.flag_type == "official_status" and f.status:
            for k in ("out", "injured reserve", "suspension", "doubtful", "questionable", "day-to-day"):
                if k in f.status:
                    st = {"injured reserve": "out", "suspension": "out", "day-to-day": "questionable"}.get(k, k)
                    break
        elif f.flag_type in ("ruled_out", "suspension"):
            st = "out"
        elif f.flag_type in ("illness", "injury", "game_time_decision", "personal", "load_management") and f.severity >= 2:
            st = "questionable"
        if st and (worst is None or order[st] > order[worst]):
            worst = st
    return worst


def verdict_for_bet(flags: list[Flag], key_players: list[str], teams: list[str], kickoff: dt.datetime,
                    recheck_lead_minutes: int = 90) -> tuple[str, str | None, list[dict]]:
    """Returns (status, recheck_time_iso, relevant_flags).
    status: OK | WAIT | VETO. Flags never upgrade a bet."""
    relevant = [f for f in flags if (f.player in key_players) or (f.player is None and (f.team in teams or f.team is None))
                or (f.team in teams and f.player in key_players)]
    status, recheck = "OK", None
    for f in relevant:
        if f.severity >= 3 and f.player in key_players and f.flag_type in ("ruled_out", "suspension", "official_status") \
                and (f.status is None or any(k in (f.status or "") for k in ("out", "injured reserve", "suspension", "doubtful"))):
            status = "VETO"
        elif f.severity >= 2 and status != "VETO":
            status = "WAIT"
    if status == "WAIT":
        # official NFL inactives ~90 min before kickoff; NBA lineups ~30 min
        recheck = (kickoff - dt.timedelta(minutes=recheck_lead_minutes)).isoformat()
    return status, recheck, [f.as_dict() for f in relevant]

"""Live + historical odds ingestion.

Reference implementation targets The Odds API (https://the-odds-api.com/),
covering spreads, totals, and moneylines across multiple books including
Pinnacle where available (used as the "sharp" reference book for de-vigging
in edge/devig.py, since Pinnacle carries the lowest vig / highest limits of
commonly-available books).

Requires: `ODDS_API_KEY` environment variable. Without it, `OddsAPIClient`
raises immediately rather than failing silently or returning fake data.

CLV requires CLOSING lines, and The Odds API (like most affordable odds
APIs) only exposes a rolling window of *current* odds, not arbitrary
historical closing lines. Two ways to get real closing-line history:
  1. Run `snapshot_and_store` on a scheduler (cron / Airflow / GH Actions)
     at fixed intervals leading up to each game's kickoff/tipoff; tag the
     last snapshot captured before game start as `snapshot_type='close'`.
     This is the free path but only starts accumulating history from when
     you start running it.
  2. Pay for a historical-odds product (The Odds API's `/historical` endpoint
     is a paid add-on; SportsDataIO also sells historical closing lines).
     `backfill_historical` below is a stub for that path — wire in your
     provider's historical endpoint the same way `OddsAPIClient` wires the
     live one.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import asdict

import requests

from data_pipeline.config import load_config, odds_api_key
from data_pipeline.db import connect
from data_pipeline.schema import OddsSnapshot


class OddsAPIClient:
    """Thin client for The Odds API v4."""

    SPORT_KEYS = {
        "NFL": "americanfootball_nfl",
        "NCAAF": "americanfootball_ncaaf",
        "NBA": "basketball_nba",
    }

    def __init__(self, api_key: str | None = None, cfg: dict | None = None):
        self.cfg = cfg or load_config()
        self.api_key = api_key or odds_api_key()
        if not self.api_key:
            raise RuntimeError(
                "ODDS_API_KEY is not set. Get a key from https://the-odds-api.com/ "
                "and `export ODDS_API_KEY=...` before pulling live odds."
            )
        self.base_url = self.cfg["odds_api"]["base_url"]

    def fetch_current_odds(self, sport: str) -> list[dict]:
        if sport not in self.SPORT_KEYS:
            raise ValueError(f"Unsupported sport {sport!r}; expected one of {list(self.SPORT_KEYS)}")
        url = f"{self.base_url}/sports/{self.SPORT_KEYS[sport]}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": self.cfg["odds_api"]["regions"],
            "markets": self.cfg["odds_api"]["markets"],
            "oddsFormat": self.cfg["odds_api"]["odds_format"],
        }
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()


def game_id_from_odds_event(sport: str, event: dict) -> str:
    # Stable synthetic ID: sport + commence_time + teams, since The Odds API's
    # event `id` is provider-internal and may not match your `games` table's
    # own game_id from the schedule source. If your schedule source's IDs are
    # derivable/joinable, prefer joining on (sport, date, home_team, away_team)
    # instead of trusting this id to match `games.game_id` verbatim.
    return f"{sport}_{event['commence_time']}_{event['home_team']}_{event['away_team']}".replace(" ", "-")


def parse_odds_api_event(sport: str, event: dict, snapshot_type: str, captured_at: str | None = None) -> list[OddsSnapshot]:
    """Flattens one Odds API event payload into per-book/per-market OddsSnapshot rows."""
    captured_at = captured_at or dt.datetime.utcnow().isoformat()
    game_id = game_id_from_odds_event(sport, event)
    home_team = event["home_team"]
    away_team = event["away_team"]
    out: list[OddsSnapshot] = []

    for book in event.get("bookmakers", []):
        book_key = book["key"]
        for market in book.get("markets", []):
            mkey = market["key"]  # 'h2h' | 'spreads' | 'totals'
            outcomes = {o["name"]: o for o in market.get("outcomes", [])}

            if mkey == "h2h":
                home_o = outcomes.get(home_team)
                away_o = outcomes.get(away_team)
                out.append(
                    OddsSnapshot(
                        game_id=game_id,
                        book=book_key,
                        snapshot_type=snapshot_type,
                        captured_at=captured_at,
                        market="moneyline",
                        home_price=home_o.get("price") if home_o else None,
                        away_price=away_o.get("price") if away_o else None,
                    )
                )
            elif mkey == "spreads":
                home_o = outcomes.get(home_team)
                away_o = outcomes.get(away_team)
                out.append(
                    OddsSnapshot(
                        game_id=game_id,
                        book=book_key,
                        snapshot_type=snapshot_type,
                        captured_at=captured_at,
                        market="spread",
                        home_price=home_o.get("price") if home_o else None,
                        away_price=away_o.get("price") if away_o else None,
                        home_point=home_o.get("point") if home_o else None,
                        away_point=away_o.get("point") if away_o else None,
                    )
                )
            elif mkey == "totals":
                over_o = outcomes.get("Over")
                under_o = outcomes.get("Under")
                out.append(
                    OddsSnapshot(
                        game_id=game_id,
                        book=book_key,
                        snapshot_type=snapshot_type,
                        captured_at=captured_at,
                        market="total",
                        home_price=over_o.get("price") if over_o else None,  # 'home_price' slot reused for Over
                        away_price=under_o.get("price") if under_o else None,  # 'away_price' slot reused for Under
                        home_point=over_o.get("point") if over_o else None,
                        away_point=under_o.get("point") if under_o else None,
                    )
                )
    return out


def store_odds_snapshots(snapshots: list[OddsSnapshot], conn: sqlite3.Connection | None = None) -> int:
    def _write(c: sqlite3.Connection):
        n = 0
        for s in snapshots:
            d = asdict(s)
            cols = ", ".join(d.keys())
            placeholders = ", ".join(f":{k}" for k in d.keys())
            c.execute(f"INSERT INTO odds_snapshots ({cols}) VALUES ({placeholders})", d)
            n += 1
        return n

    if conn is not None:
        return _write(conn)
    with connect() as c:
        return _write(c)


def snapshot_and_store(sport: str, snapshot_type: str = "live", client: OddsAPIClient | None = None) -> int:
    """Pulls current odds for a sport and stores them tagged with
    `snapshot_type` ('open'/'close'/'live'). Run this on a scheduler; tag the
    call closest to (but before) kickoff as 'close' so CLV has a real closing
    line to compare against.
    """
    client = client or OddsAPIClient()
    events = client.fetch_current_odds(sport)
    captured_at = dt.datetime.utcnow().isoformat()
    all_snaps: list[OddsSnapshot] = []
    for event in events:
        all_snaps.extend(parse_odds_api_event(sport, event, snapshot_type, captured_at))
    return store_odds_snapshots(all_snaps)


def backfill_historical(sport: str, start_date: str, end_date: str) -> int:
    """Stub for a paid historical-odds backfill. Implement against your
    provider's historical endpoint (e.g. The Odds API's `/historical/sports/
    {sport}/odds` with a `date` param, or SportsDataIO's historical odds
    endpoint) and call `store_odds_snapshots` the same way `snapshot_and_store`
    does. Left unimplemented here because it requires a paid subscription
    this repo cannot assume you have.
    """
    raise NotImplementedError(
        "backfill_historical requires a paid historical-odds provider. "
        "Implement this against your subscription's historical endpoint, "
        "following the OddsAPIClient pattern above."
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pull and store current odds for a sport.")
    parser.add_argument("sport", choices=["NFL", "NCAAF", "NBA"])
    parser.add_argument("--snapshot-type", default="live", choices=["open", "close", "live"])
    args = parser.parse_args()
    n = snapshot_and_store(args.sport, args.snapshot_type)
    print(f"Stored {n} odds rows for {args.sport} ({args.snapshot_type})")

"""Cross-book arbitrage scanner CLI.

Run as: python scripts/arb_scan.py [--sport NFL] [--live] [--stake 1000]
                                    [--staleness-threshold 60] [--csv PATH]

This is pure price math (arbitrage/ module): for each game/market/line, it
finds the best available price per outcome across ALL books in the odds
source, sums their raw (vig-included) implied probabilities, and flags a
true arbitrage whenever that sum is under 100%. It does not predict, rank,
or recommend a side — either a riskless cross-book price gap exists or it
doesn't. An empty result table is the expected, common outcome; the scan
prints that plainly rather than lowering any bar to manufacture a result.

Two data sources:
  --live     Pulls odds fresh via OddsAPIClient (needs ODDS_API_KEY — see
             README). A single API call returns every book's current price
             for a sport in one shot, so the legs of any flagged arb share
             (almost) the same captured_at and the freshness gap is ~0.
  (default)  Reads the latest stored 'live' snapshot per book from the
             local DB, as populated by running data_pipeline/ingest_odds.py
             on a scheduler. This is where the freshness flag actually
             earns its keep: a book that failed to refresh on the most
             recent scheduled pull shows an older captured_at than the
             rest, and the gap between them is real execution risk.
"""
from __future__ import annotations

import argparse
import datetime as dt

import pandas as pd

from data_pipeline.config import SPORTS
from data_pipeline.db import connect
from data_pipeline.ingest_odds import OddsAPIClient, parse_odds_api_event, game_id_from_odds_event
from data_pipeline.queries import load_latest_snapshot_per_book
from data_pipeline.schema import OddsSnapshot
from arbitrage.arb_scanner import (
    scan_game,
    opportunities_to_frame,
    DEFAULT_STALENESS_THRESHOLD_SECONDS,
    LIQUIDITY_CAVEAT,
    MARKETS,
)


def _snapshots_from_frame(df: pd.DataFrame) -> list[OddsSnapshot]:
    return [
        OddsSnapshot(
            game_id=r.game_id, book=r.book, snapshot_type=r.snapshot_type, captured_at=r.captured_at,
            market=r.market, home_price=r.home_price, away_price=r.away_price,
            home_point=r.home_point, away_point=r.away_point,
        )
        for r in df.itertuples()
    ]


def scan_live(sport: str, stake: float, staleness_threshold: float) -> pd.DataFrame:
    client = OddsAPIClient()  # raises RuntimeError if ODDS_API_KEY isn't set
    events = client.fetch_current_odds(sport)
    now_iso = dt.datetime.utcnow().isoformat()
    all_opps = []
    for event in events:
        gid = game_id_from_odds_event(sport, event)
        snapshots = parse_odds_api_event(sport, event, "live", now_iso)
        all_opps.extend(
            scan_game(snapshots, sport, gid, event["home_team"], event["away_team"], stake, staleness_threshold)
        )
    return opportunities_to_frame(all_opps)


def scan_from_db(sport: str, stake: float, staleness_threshold: float) -> pd.DataFrame:
    all_opps = []
    with connect() as conn:
        games = pd.read_sql_query(
            "SELECT game_id, home_team, away_team FROM games WHERE sport = ?", conn, params=(sport,)
        )
        game_lookup = games.set_index("game_id")[["home_team", "away_team"]].to_dict("index")

        for market in MARKETS:
            df = load_latest_snapshot_per_book(conn, sport, market)
            if df.empty:
                continue
            for gid, grp in df.groupby("game_id"):
                if gid not in game_lookup:
                    continue
                snapshots = _snapshots_from_frame(grp)
                all_opps.extend(
                    scan_game(
                        snapshots, sport, gid,
                        game_lookup[gid]["home_team"], game_lookup[gid]["away_team"],
                        stake, staleness_threshold, markets=(market,),
                    )
                )
    return opportunities_to_frame(all_opps)


def run_scan(sports: list[str], stake: float, staleness_threshold: float, live: bool) -> pd.DataFrame:
    frames = []
    for sport in sports:
        try:
            df = scan_live(sport, stake, staleness_threshold) if live else scan_from_db(sport, stake, staleness_threshold)
        except RuntimeError as e:
            print(f"{sport}: SKIPPED — {e}")
            continue
        frames.append(df)

    result = pd.concat(frames, ignore_index=True) if frames else opportunities_to_frame([])
    if not result.empty:
        result = result.sort_values("arb_margin_pct", ascending=False).reset_index(drop=True)
    return result


def print_report(result: pd.DataFrame, staleness_threshold: float) -> None:
    print(f"\n{'=' * 90}\nARBITRAGE SCAN — {dt.datetime.utcnow().isoformat()}Z (UTC)\n{'=' * 90}")

    if result.empty:
        print("\nNo cross-book arbitrage opportunities found on this scan. This is the expected, common result.")
        return

    display = result.copy()
    display["arb_margin_pct"] = display["arb_margin_pct"].map(lambda x: f"{x:.2%}")
    display["guaranteed_profit"] = display["guaranteed_profit"].map(lambda x: f"${x:,.2f}")
    print(f"\n{len(result)} opportunity(ies) found:\n")
    print(display.to_string(index=False))

    n_stale = int(result["stale"].sum())
    if n_stale:
        print(
            f"\nWARNING: {n_stale} result(s) flagged STALE — more than the {staleness_threshold:.0f}s "
            "threshold passed between the two legs' odds pulls. Books move fast; a stale arb may already "
            "be gone. Re-verify both prices before staking anything."
        )

    print(f"\nNOTE: {LIQUIDITY_CAVEAT}")


def main():
    parser = argparse.ArgumentParser(description="Cross-book arbitrage scanner across NFL/NCAAF/NBA.")
    parser.add_argument("--sport", choices=SPORTS, default=None, help="Restrict to one sport; default scans all.")
    parser.add_argument(
        "--live", action="store_true",
        help="Pull fresh odds via the Odds API instead of reading the local DB (needs ODDS_API_KEY).",
    )
    parser.add_argument("--stake", type=float, default=1000.0, help="Total stake to split across an arb's legs.")
    parser.add_argument(
        "--staleness-threshold", type=float, default=DEFAULT_STALENESS_THRESHOLD_SECONDS,
        help="Seconds between an opportunity's two legs' odds pulls beyond which it's flagged stale.",
    )
    parser.add_argument("--csv", default=None, help="Optional path to also write results as CSV.")
    args = parser.parse_args()

    sports = [args.sport] if args.sport else list(SPORTS)
    result = run_scan(sports, args.stake, args.staleness_threshold, args.live)
    print_report(result, args.staleness_threshold)

    if args.csv and not result.empty:
        result.to_csv(args.csv, index=False)
        print(f"\nWrote {len(result)} rows to {args.csv}")


if __name__ == "__main__":
    main()

"""`edgecard` command line.

  edgecard ingest   --league nfl|nba [--seasons 2015-2026]
  edgecard backtest --league nfl|nba
  edgecard snapshot --league nfl|nba|both          (odds + props from every free book)
  edgecard today    --league nfl|nba|both [--mode full|recheck]
  edgecard settle   --league nfl|nba|both          (closing lines, results, CLV)
  edgecard report                                   (weekly CLV / ROI / calibration)
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys


def _seasons(spec: str) -> list[int]:
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",")]


def _leagues(arg: str) -> list[str]:
    return ["NFL", "NBA"] if arg == "both" else [arg.upper()]


def cmd_ingest(args) -> int:
    today = dt.date.today()
    if "NFL" in _leagues(args.league):
        from data_pipeline.sources.nflverse_hist import build_history

        nfl_now = today.year if today.month >= 8 else today.year - 1
        seasons = _seasons(args.seasons) if args.seasons else list(range(2015, nfl_now + 1))
        print(f"NFL ingest {seasons[0]}-{seasons[-1]}")
        print(build_history(seasons, include_pbp=not args.no_pbp))
    if "NBA" in _leagues(args.league):
        from data_pipeline.sources.nba_free import build_history as nba_build

        nba_now = today.year if today.month >= 10 else today.year - 1
        seasons = _seasons(args.seasons) if args.seasons else list(range(nba_now - 6, nba_now + 1))
        print(f"NBA ingest {seasons[0]}-{seasons[-1]} (season = starting year)")
        print(nba_build(seasons))
    return 0


def cmd_backtest(args) -> int:
    from edgecard.backtest import run_backtest

    for lg in _leagues(args.league):
        run_backtest(lg, quick=args.quick)
    return 0


def cmd_snapshot(args) -> int:
    from edgecard.odds import snapshot_all

    for lg in _leagues(args.league):
        snapshot_all(lg, tag=args.tag)
    return 0


def cmd_today(args) -> int:
    from edgecard.card import build_and_publish

    return build_and_publish(_leagues(args.league), mode=args.mode, bankroll=args.bankroll)


def cmd_settle(args) -> int:
    from edgecard.tracking import settle

    for lg in _leagues(args.league):
        settle(lg)
    return 0


def cmd_report(args) -> int:
    from edgecard.tracking import weekly_report

    rep = weekly_report()
    print(rep.get("headline", ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="edgecard", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest")
    p.add_argument("--league", default="nfl", choices=["nfl", "nba", "both"])
    p.add_argument("--seasons", default=None)
    p.add_argument("--no-pbp", action="store_true")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("backtest")
    p.add_argument("--league", default="nfl", choices=["nfl", "nba", "both"])
    p.add_argument("--quick", action="store_true", help="fewer test seasons, for smoke runs")
    p.set_defaults(fn=cmd_backtest)

    p = sub.add_parser("snapshot")
    p.add_argument("--league", default="both", choices=["nfl", "nba", "both"])
    p.add_argument("--tag", default="live", choices=["live", "close"])
    p.set_defaults(fn=cmd_snapshot)

    p = sub.add_parser("today")
    p.add_argument("--league", default="both", choices=["nfl", "nba", "both"])
    p.add_argument("--mode", default="full", choices=["full", "recheck"])
    p.add_argument("--bankroll", type=float, default=None)
    p.set_defaults(fn=cmd_today)

    p = sub.add_parser("settle")
    p.add_argument("--league", default="both", choices=["nfl", "nba", "both"])
    p.set_defaults(fn=cmd_settle)

    p = sub.add_parser("report")
    p.set_defaults(fn=cmd_report)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

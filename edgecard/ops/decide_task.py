"""Decides what a scheduled pipeline run should do, from the current time in
New York and what's already in the data store.

GitHub cron is UTC-only and doesn't know about daylight saving, so every
slot is scheduled at both its EDT and EST UTC hour; this script drops the
one that lands at the wrong local time, and also drops a duplicate if the
day's run already happened (so a delayed cron firing twice is harmless).

Prints one of: full | recheck | close | skip   (to stdout, for $GITHUB_OUTPUT)
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo


def decide(now_utc: dt.datetime, store: Path, requested: str = "auto") -> str:
    if requested == "none":
        return "skip"
    if requested and requested != "auto":
        return requested
    et = now_utc.astimezone(ZoneInfo("America/New_York"))
    day = et.date().isoformat()
    minutes = et.hour * 60 + et.minute
    done = lambda run: (store / "cards" / day / f"{run}.json").exists()  # noqa: E731
    if 9 * 60 + 30 <= minutes < 12 * 60:
        return "skip" if done("full") else "full"
    if 16 * 60 + 30 <= minutes < 19 * 60:
        return "skip" if done("recheck") else "recheck"
    return "close"  # every other scheduled slot is a pre-game line capture


if __name__ == "__main__":
    store = Path(os.environ.get("EDGECARD_DATA_DIR", "."))
    req = sys.argv[1] if len(sys.argv) > 1 else "auto"
    print(decide(dt.datetime.now(dt.timezone.utc), store, req))

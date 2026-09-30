"""Per-run data freshness log. Every source call records whether it worked,
how many rows it returned, and when — so the card (and the site) can show
exactly how fresh each input was, and a stale or failed source is visible
instead of silently producing a card from old data."""
from __future__ import annotations

import datetime as dt

from edgecard import store

_RUN: dict[str, dict] = {}


def record(source: str, ok: bool, n: int = 0, note: str = "", as_of: str | None = None) -> None:
    _RUN[source] = {
        "ok": bool(ok),
        "rows": int(n),
        "note": note,
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "data_as_of": as_of,
    }


def current() -> dict[str, dict]:
    return dict(_RUN)


def flush() -> dict:
    prev = store.read_json("freshness", "latest.json", default={}) or {}
    prev.update(_RUN)
    store.write_json(prev, "freshness", "latest.json")
    return prev

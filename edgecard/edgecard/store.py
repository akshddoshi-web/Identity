"""File-based results store.

All durable state lives in a directory (`EDGECARD_DATA_DIR`, default
edgecard/data/store). In production that directory is a checkout of the
repo's `edgecard-data` branch: GitHub Actions writes to it and commits, and
the Streamlit app reads the same files over raw.githubusercontent.com. No
database server, no paid storage.

Layout:
  history/*.parquet                 point-in-time training history (ingest job)
  odds/<league>/<date>.parquet      every odds snapshot pulled that day (all books)
  props/<league>/<date>.parquet     every player-prop line snapshot pulled that day
  cards/<date>/<run>.json           each card as published
  cards/latest.json                 newest card (what the site shows)
  ledger/recommendations.csv        append-only log of every recommendation
  ledger/settlements.csv            closing line, result, CLV per recommendation
  reports/*.json                    backtest + weekly tracking reports
  freshness/latest.json             per-source freshness for the latest run
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import pandas as pd

from data_pipeline.config import REPO_ROOT


def data_dir() -> Path:
    p = Path(os.environ.get("EDGECARD_DATA_DIR", REPO_ROOT / "data" / "store"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def path(*parts: str) -> Path:
    p = data_dir().joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def history_path(name: str) -> Path:
    return path("history", f"{name}.parquet")


def write_json(obj, *parts: str) -> Path:
    p = path(*parts)
    p.write_text(json.dumps(obj, indent=1, default=str))
    return p


def read_json(*parts: str, default=None):
    p = data_dir().joinpath(*parts)
    if not p.exists():
        return default
    return json.loads(p.read_text())


def append_parquet(df: pd.DataFrame, *parts: str) -> Path:
    """Appends rows to a parquet file (read-concat-write; files are per-day
    so they stay small)."""
    p = path(*parts)
    if p.exists() and len(df):
        old = pd.read_parquet(p)
        df = pd.concat([old, df], ignore_index=True)
    if len(df):
        df.to_parquet(p, index=False)
    return p


def read_parquet_glob(pattern_dir: tuple[str, ...], since: dt.date | None = None) -> pd.DataFrame:
    d = data_dir().joinpath(*pattern_dir)
    if not d.exists():
        return pd.DataFrame()
    frames = []
    for f in sorted(d.glob("*.parquet")):
        if since is not None:
            try:
                if dt.date.fromisoformat(f.stem) < since:
                    continue
            except ValueError:
                pass
        frames.append(pd.read_parquet(f))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def append_csv(df: pd.DataFrame, *parts: str) -> Path:
    p = path(*parts)
    header = not p.exists()
    df.to_csv(p, mode="a", header=header, index=False)
    return p


def read_csv(*parts: str) -> pd.DataFrame:
    p = data_dir().joinpath(*parts)
    return pd.read_csv(p) if p.exists() else pd.DataFrame()

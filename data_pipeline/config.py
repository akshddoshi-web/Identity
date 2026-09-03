"""Config loading shared by every module. Single source of truth: config/config.yaml."""
from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"


@functools.lru_cache(maxsize=None)
def load_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(cfg_path, "r") as f:
        return yaml.safe_load(f)


def db_path(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or load_config()
    p = Path(cfg["database"]["path"])
    if not p.is_absolute():
        p = REPO_ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def odds_api_key() -> str | None:
    """Returns the configured Odds API key, or None if not set.

    Never hardcode a key in this repo. Set the ODDS_API_KEY environment
    variable before running any live ingestion.
    """
    return os.environ.get("ODDS_API_KEY")


SPORTS = ("NFL", "NCAAF", "NBA")

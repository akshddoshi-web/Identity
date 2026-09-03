"""Config loading shared by every module. Single source of truth: config/config.yaml."""
from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"

# Loads a local .env file (repo root) into os.environ, if one exists —
# this is how ODDS_API_KEY reaches the process when running locally. See
# README's "Odds API key setup" section for exactly where this file goes.
# A no-op if python-dotenv isn't installed or no .env is present, so this
# never breaks a deployment that supplies the key another way (a real
# exported env var, or Streamlit Cloud's secrets store — see
# odds_api_key() below).
try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass


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

    Never hardcode a key in this repo. Checked in order:
      1. The ODDS_API_KEY environment variable (set directly, or loaded
         from a local .env file — see the load_dotenv() call above).
      2. Streamlit Cloud's secrets store (st.secrets["ODDS_API_KEY"]),
         when running as a deployed Streamlit app that has a key configured
         under Settings -> Secrets. This branch is a no-op everywhere else
         (plain scripts, tests, local runs without streamlit installed) —
         it only fires when `streamlit` is importable AND actually running
         inside a Streamlit script, so it never raises for callers that
         aren't Streamlit.
    """
    key = os.environ.get("ODDS_API_KEY")
    if key:
        return key
    try:
        import streamlit as st

        return st.secrets.get("ODDS_API_KEY")
    except Exception:
        return None


SPORTS = ("NFL", "NCAAF", "NBA")

"""NBA hooks for the card. Until the NBA model is backtested
(`edgecard backtest --league nba`, which writes models/nba_game.pkl), the
NBA card is market-only: fair value = multi-book no-vig consensus, and the
only bets are line-shopping edges."""
from __future__ import annotations

import pandas as pd


def run_nba_backtest(quick: bool = False) -> dict:
    from edgecard.nba_model import run_nba_backtest as _run

    return _run(quick=quick)


def nba_model_means(events: pd.DataFrame, lp) -> dict:
    try:
        from edgecard.nba_model import live_means
    except ImportError:
        return {}
    return live_means(events, lp)


def nba_key_players(teams: list[str]) -> list[tuple[str, str]]:
    try:
        from edgecard.nba_model import key_players
    except ImportError:
        return []
    return key_players(teams)

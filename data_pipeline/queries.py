"""Shared read queries against the SQLite store. Factored out of
scripts/run_pipeline_demo.py so both the backtest demo and
scripts/daily_report.py read games/stats/odds the exact same way — a
mismatch between how training data and live data are loaded is a classic
source of silent train/serve skew.
"""
from __future__ import annotations

import sqlite3

import pandas as pd


def load_games(conn: sqlite3.Connection, sport: str) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT * FROM games WHERE sport = ? ORDER BY game_date, game_id", conn, params=(sport,)
    )


def load_team_game_stats(conn: sqlite3.Connection, sport: str) -> pd.DataFrame:
    return pd.read_sql_query(
        """SELECT tgs.* FROM team_game_stats tgs
           JOIN games g ON g.game_id = tgs.game_id
           WHERE g.sport = ?""",
        conn,
        params=(sport,),
    )


def load_odds_snapshots(
    conn: sqlite3.Connection,
    sport: str,
    market: str,
    snapshot_type: str,
    book: str | None = None,
) -> pd.DataFrame:
    query = """SELECT o.* FROM odds_snapshots o
               JOIN games g ON g.game_id = o.game_id
               WHERE g.sport = ? AND o.market = ? AND o.snapshot_type = ?"""
    params: list = [sport, market, snapshot_type]
    if book is not None:
        query += " AND o.book = ?"
        params.append(book)
    return pd.read_sql_query(query, conn, params=params)


def load_latest_snapshot_per_book(
    conn: sqlite3.Connection, sport: str, market: str, snapshot_type: str = "live"
) -> pd.DataFrame:
    """Latest snapshot per (game_id, book) for a market/snapshot_type — the
    price actually in effect right now at each book, even if some books were
    last refreshed at a different real time than others (e.g. one book
    failed on the most recent scheduled pull and its last-known price is
    older). That gap is exactly what arbitrage/arb_scanner.py's staleness
    flag is checking for, so this reads "latest per book", not "latest
    overall" — a plain MAX(captured_at) across all rows would collapse
    every book onto one pull and hide the gap.
    """
    return pd.read_sql_query(
        """
        SELECT o.* FROM odds_snapshots o
        JOIN games g ON g.game_id = o.game_id
        JOIN (
            SELECT game_id, book, MAX(captured_at) AS max_captured_at
            FROM odds_snapshots
            WHERE market = ? AND snapshot_type = ?
            GROUP BY game_id, book
        ) latest ON latest.game_id = o.game_id AND latest.book = o.book AND latest.max_captured_at = o.captured_at
        WHERE g.sport = ? AND o.market = ? AND o.snapshot_type = ?
        """,
        conn,
        params=(market, snapshot_type, sport, market, snapshot_type),
    )


def bet_ledger_all(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM bet_ledger ORDER BY placed_at", conn)

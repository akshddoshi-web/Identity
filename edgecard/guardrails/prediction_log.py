"""Immutable, timestamped prediction logging.

This is the anti-cherry-picking guardrail. The single easiest way for any
backtest-driven system to look better than it is is to let "predictions"
be written or edited after the fact, even accidentally (e.g. re-running a
notebook cell after seeing results). This module makes that hard:

  - `log_prediction` INSERTs (never UPDATEs) into `predictions`, keyed by a
    content hash (`prediction_id`) of (game_id, model_name, model_version,
    market, side-relevant fields) so re-running the same prediction is
    idempotent (SQLite raises on the UNIQUE constraint) rather than silently
    overwriting an earlier number.
  - Every row carries `predicted_at` (wall-clock time of the INSERT) AND
    `game_start_at`. `assert_logged_before_game_start` is called at
    settlement time and raises if a prediction's `predicted_at` is not
    strictly before its `game_start_at` — i.e., it refuses to let a
    post-hoc prediction be treated as pre-game.
  - There is deliberately no `update_prediction` / `delete_prediction`
    function exported from this module. If you truly need to correct a bad
    row (e.g. a data pipeline bug wrote garbage), do it via a documented,
    logged correction script that inserts a new row referencing the old one
    — never edit history in place.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import sqlite3

from data_pipeline.db import connect


class PreGameLockViolation(Exception):
    """Raised when a prediction's predicted_at is not strictly before its
    game_start_at — i.e., someone tried to log or backdate a prediction
    after the game already started."""


def make_prediction_id(game_id: str, model_name: str, model_version: str, market: str, side: str) -> str:
    raw = f"{game_id}|{model_name}|{model_version}|{market}|{side}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def log_prediction(
    *,
    game_id: str,
    sport: str,
    model_name: str,
    model_version: str,
    market: str,
    side: str,
    game_start_at: str,
    model_prob_home: float | None = None,
    model_margin: float | None = None,
    model_total: float | None = None,
    market_home_price: float | None = None,
    market_away_price: float | None = None,
    market_point: float | None = None,
    market_book: str | None = None,
    market_devigged_prob_home: float | None = None,
    edge: float | None = None,
    flagged: bool = False,
    conn: sqlite3.Connection | None = None,
    _now_override: str | None = None,
) -> str:
    """Logs one prediction. Raises PreGameLockViolation if `game_start_at`
    is already in the past relative to now — this system does not allow
    logging a prediction for a game that has already started, because that
    could not have been a real pre-game prediction.

    `_now_override` exists only for tests that need deterministic clocks;
    do not use it in application code.
    """
    now = _now_override or dt.datetime.utcnow().isoformat()
    if _parse(now) >= _parse(game_start_at):
        raise PreGameLockViolation(
            f"Refusing to log a prediction for game_start_at={game_start_at} "
            f"at predicted_at={now}: game has already started or start time is invalid."
        )

    prediction_id = make_prediction_id(game_id, model_name, model_version, market, side)

    def _write(c: sqlite3.Connection):
        c.execute(
            """INSERT INTO predictions (
                prediction_id, game_id, sport, model_name, model_version, market,
                predicted_at, game_start_at, model_prob_home, model_margin, model_total,
                market_home_price, market_away_price, market_point, market_book,
                market_devigged_prob_home, edge, flagged, locked
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                prediction_id,
                game_id,
                sport,
                model_name,
                model_version,
                market,
                now,
                game_start_at,
                model_prob_home,
                model_margin,
                model_total,
                market_home_price,
                market_away_price,
                market_point,
                market_book,
                market_devigged_prob_home,
                edge,
                int(flagged),
            ),
        )

    if conn is not None:
        _write(conn)
    else:
        with connect() as c:
            _write(c)
    return prediction_id


def _parse(iso_str: str) -> dt.datetime:
    s = iso_str.replace("Z", "+00:00")
    d = dt.datetime.fromisoformat(s)
    return d.replace(tzinfo=None) if d.tzinfo else d


def assert_logged_before_game_start(predicted_at: str, game_start_at: str) -> None:
    if _parse(predicted_at) >= _parse(game_start_at):
        raise PreGameLockViolation(
            f"Prediction logged at {predicted_at} is not strictly before game start {game_start_at}."
        )

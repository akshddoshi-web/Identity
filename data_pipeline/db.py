"""SQLite storage layer.

Design goals:
  - One file DB (fine for a single-analyst / small-team deployment; swap the
    connection string for Postgres if you outgrow SQLite — the schema is
    plain ANSI SQL and doesn't use SQLite-only features other than
    `INTEGER PRIMARY KEY` autoincrement).
  - `predictions` table is APPEND-ONLY at the application layer (see
    guardrails/prediction_log.py). The DB itself doesn't enforce
    immutability (SQLite has no row-level ACLs), so the *only* code path
    that should ever UPDATE or DELETE from `predictions` is a documented
    correction workflow — never routine app code.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from data_pipeline.config import db_path, load_config

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    game_id         TEXT PRIMARY KEY,
    sport           TEXT NOT NULL,               -- NFL / NCAAF / NBA
    season          INTEGER NOT NULL,
    week            INTEGER,                      -- NULL for NBA
    game_date       TEXT NOT NULL,                 -- ISO date, gametime
    home_team       TEXT NOT NULL,
    away_team       TEXT NOT NULL,
    home_score      INTEGER,                       -- NULL until final
    away_score      INTEGER,
    is_final        INTEGER NOT NULL DEFAULT 0,
    neutral_site    INTEGER NOT NULL DEFAULT 0,
    home_rest_days  INTEGER,
    away_rest_days  INTEGER,
    home_travel_mi  REAL,
    away_travel_mi  REAL,
    referee_crew    TEXT,
    weather_temp_f  REAL,
    weather_wind_mph REAL,
    weather_precip  TEXT,                          -- none/rain/snow
    is_dome         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS injuries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(game_id),
    team            TEXT NOT NULL,
    player          TEXT NOT NULL,
    position        TEXT,
    status          TEXT NOT NULL,                 -- out/doubtful/questionable/probable
    impact_score    REAL,                           -- provider-specific 0-1 severity weight
    report_date     TEXT
);

CREATE TABLE IF NOT EXISTS team_game_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(game_id),
    team            TEXT NOT NULL,
    is_home         INTEGER NOT NULL,
    -- football (NFL/NCAAF) advanced stats, NULL for NBA rows
    epa_per_play        REAL,
    success_rate         REAL,
    pass_epa_per_play     REAL,
    rush_epa_per_play     REAL,
    red_zone_pct           REAL,
    third_down_pct          REAL,
    pressure_rate            REAL,
    pff_off_grade             REAL,
    pff_def_grade             REAL,
    -- basketball (NBA) advanced stats, NULL for football
    off_rating              REAL,
    def_rating               REAL,
    pace                      REAL,
    efg_pct                   REAL,
    tov_pct                    REAL,
    orb_pct                     REAL,
    ftr                          REAL,
    net_rating_lineup_wtd         REAL,
    UNIQUE(game_id, team)
);

CREATE TABLE IF NOT EXISTS odds_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(game_id),
    book            TEXT NOT NULL,
    snapshot_type   TEXT NOT NULL,                 -- 'open' | 'close' | 'live'
    captured_at     TEXT NOT NULL,                 -- ISO timestamp of snapshot
    market          TEXT NOT NULL,                 -- 'spread' | 'total' | 'moneyline'
    home_price      REAL,                           -- american odds, home/over side
    away_price      REAL,                           -- american odds, away/under side
    home_point      REAL,                           -- spread or total line value (home-relative)
    away_point      REAL
);

CREATE TABLE IF NOT EXISTS predictions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id       TEXT UNIQUE NOT NULL,        -- content hash, for idempotent writes
    game_id             TEXT NOT NULL REFERENCES games(game_id),
    sport               TEXT NOT NULL,
    model_name          TEXT NOT NULL,
    model_version       TEXT NOT NULL,
    market              TEXT NOT NULL,               -- spread | total | moneyline
    predicted_at        TEXT NOT NULL,               -- wall-clock timestamp, LOGGED PRE-GAME
    game_start_at        TEXT NOT NULL,
    model_prob_home       REAL,                       -- model win prob (moneyline) or cover prob (spread)
    model_margin           REAL,                       -- predicted home margin (spread models)
    model_total             REAL,                       -- predicted total (total models)
    market_home_price        REAL,
    market_away_price          REAL,
    market_point                 REAL,
    market_book                   TEXT,
    market_devigged_prob_home      REAL,
    edge                             REAL,             -- model_prob_home - market_devigged_prob_home
    flagged                           INTEGER NOT NULL DEFAULT 0,
    locked                             INTEGER NOT NULL DEFAULT 1  -- 1 once game_start_at has passed; enforced by app layer
);

CREATE TABLE IF NOT EXISTS clv_records (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id        TEXT NOT NULL REFERENCES predictions(prediction_id),
    bet_price              REAL NOT NULL,             -- american odds at time of bet
    bet_point                REAL,
    closing_price              REAL,
    closing_point                REAL,
    clv_prob_pct                  REAL,               -- (devigged closing prob - devigged bet-time prob), in prob pts
    recorded_at                     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bet_ledger (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id        TEXT NOT NULL REFERENCES predictions(prediction_id),
    placed_at              TEXT NOT NULL,
    stake                    REAL NOT NULL,
    kelly_fraction_used        REAL NOT NULL,
    bankroll_before               REAL NOT NULL,
    price                          REAL NOT NULL,      -- american odds taken
    result                          TEXT,               -- win/loss/push, NULL until settled
    settled_at                       TEXT,
    payout                            REAL,             -- net profit/loss, NULL until settled
    bankroll_after                     REAL
);

CREATE INDEX IF NOT EXISTS idx_games_sport_season ON games(sport, season);
CREATE INDEX IF NOT EXISTS idx_odds_game ON odds_snapshots(game_id);
CREATE INDEX IF NOT EXISTS idx_predictions_game ON predictions(game_id);
CREATE INDEX IF NOT EXISTS idx_clv_prediction ON clv_records(prediction_id);
CREATE INDEX IF NOT EXISTS idx_ledger_prediction ON bet_ledger(prediction_id);
"""


def get_connection(path: Path | None = None) -> sqlite3.Connection:
    p = path or db_path(load_config())
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(path: Path | None = None) -> None:
    conn = get_connection(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = get_connection(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Initialized database at {db_path(load_config())}")

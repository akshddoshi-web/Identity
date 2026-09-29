"""Closing Line Value (CLV) tracking.

CLV is the gap between the de-vigged implied probability at the time you bet
and the de-vigged implied probability at closing (the market's final,
most-informed price). Positive average CLV — consistently getting a better
number than the closing line — is the best available predictor of long-run
profitability, better than short-run win rate, because win/loss outcomes are
dominated by variance over any sample you can realistically hold in your
head, while CLV is dominated by whether you actually identified real
mispricings before the market corrected.

This module:
  1. Records CLV for every settled prediction (`record_clv`), independent of
     whether the bet won or lost — CLV is about the price, not the outcome.
  2. Aggregates CLV with a confidence interval and REFUSES to call a result
     "significant" under `min_sample_size_for_significance` (default 200,
     see config/config.yaml) — it still shows the number, just loudly
     labeled as not meaningful yet.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from data_pipeline.config import load_config
from data_pipeline.db import connect
from edge.devig import devig


@dataclass
class CLVSummary:
    n: int
    mean_clv_pct: float           # in probability points, e.g. 0.021 = +2.1pp
    std_clv_pct: float
    ci_low: float
    ci_high: float
    confidence_level: float
    is_significant_sample: bool
    min_required: int

    def headline(self) -> str:
        sig = "" if self.is_significant_sample else " [SAMPLE TOO SMALL — NOT STATISTICALLY MEANINGFUL]"
        return (
            f"CLV: {self.mean_clv_pct:+.2%} avg (n={self.n}, "
            f"{self.confidence_level:.0%} CI [{self.ci_low:+.2%}, {self.ci_high:+.2%}]){sig}"
        )


def american_implied(price: float) -> float:
    if price > 0:
        return 100.0 / (price + 100.0)
    return -price / (-price + 100.0)


def compute_clv_for_bet(
    bet_price: float,
    closing_price_side: float,
    closing_price_other_side: float,
    devig_method: str = "multiplicative",
) -> float:
    """Returns CLV in probability points: de-vigged closing implied prob for
    the side bet, minus the RAW (vig-included) implied prob at the price
    actually taken. Positive = you beat the closing line (good).

    We deliberately do NOT de-vig the bet-time price here, because at bet
    time you only ever transact at one book's single-sided price — de-vigging
    would require that book's simultaneous other-side price, which is a
    different (and legitimate) comparison handled by edge_detection.py. CLV
    asks a narrower question: "given the price I actually got, did the
    market's final, de-vigged assessment move in my favor?" so only the
    closing side is de-vigged.
    """
    closing_devig = devig(closing_price_side, closing_price_other_side, method=devig_method)
    return closing_devig.prob_a - american_implied(bet_price)


def record_clv(
    prediction_id: str,
    bet_price: float,
    bet_point: float | None,
    closing_price_home: float,
    closing_price_away: float,
    conn: sqlite3.Connection | None = None,
) -> float:
    """Computes and persists CLV for one prediction once the closing line is
    known. `closing_price_home`/`closing_price_away` are the closing prices
    for the SAME two-way market the bet was placed on (already oriented so
    'home' matches the side the bet was on as price_a).
    """
    dv = devig(closing_price_home, closing_price_away, method="multiplicative")
    clv_prob_pct = dv.prob_a - american_implied(bet_price)

    def _write(c: sqlite3.Connection):
        c.execute(
            """INSERT INTO clv_records
               (prediction_id, bet_price, bet_point, closing_price, closing_point, clv_prob_pct, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                prediction_id,
                bet_price,
                bet_point,
                closing_price_home,
                None,
                clv_prob_pct,
                dt.datetime.utcnow().isoformat(),
            ),
        )

    if conn is not None:
        _write(conn)
    else:
        with connect() as c:
            _write(c)
    return clv_prob_pct


def summarize_clv(
    clv_values: pd.Series | np.ndarray, cfg: dict | None = None
) -> CLVSummary:
    cfg = cfg or load_config()
    min_required = cfg["edge_detection"]["min_sample_size_for_significance"]
    confidence = cfg["edge_detection"]["confidence_level"]

    vals = np.asarray(clv_values, dtype=float)
    vals = vals[~np.isnan(vals)]
    n = len(vals)
    if n == 0:
        return CLVSummary(0, 0.0, 0.0, 0.0, 0.0, confidence, False, min_required)

    mean = float(vals.mean())
    std = float(vals.std(ddof=1)) if n > 1 else 0.0
    if n > 1:
        se = std / np.sqrt(n)
        t_crit = stats.t.ppf(1 - (1 - confidence) / 2, df=n - 1)
        ci_low, ci_high = mean - t_crit * se, mean + t_crit * se
    else:
        ci_low = ci_high = mean

    return CLVSummary(
        n=n,
        mean_clv_pct=mean,
        std_clv_pct=std,
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        confidence_level=confidence,
        is_significant_sample=n >= min_required,
        min_required=min_required,
    )


def clv_by_sport_and_market(conn: sqlite3.Connection | None = None, cfg: dict | None = None) -> pd.DataFrame:
    """Joins clv_records back to predictions to break CLV down by sport and
    market, each with its own CLVSummary (and its own small-sample flag —
    a sport with 400 total bets but only 60 total-market bets should show
    the total-market slice as not-yet-significant even though the sport
    overall might be)."""
    query = """
        SELECT p.sport, p.market, c.clv_prob_pct
        FROM clv_records c
        JOIN predictions p ON p.prediction_id = c.prediction_id
    """
    if conn is not None:
        df = pd.read_sql_query(query, conn)
    else:
        with connect() as c:
            df = pd.read_sql_query(query, c)

    if df.empty:
        return pd.DataFrame(columns=["sport", "market", "n", "mean_clv_pct", "ci_low", "ci_high", "is_significant_sample"])

    rows = []
    for (sport, market), g in df.groupby(["sport", "market"]):
        summary = summarize_clv(g["clv_prob_pct"], cfg)
        rows.append(
            {
                "sport": sport,
                "market": market,
                "n": summary.n,
                "mean_clv_pct": summary.mean_clv_pct,
                "ci_low": summary.ci_low,
                "ci_high": summary.ci_high,
                "is_significant_sample": summary.is_significant_sample,
            }
        )
    return pd.DataFrame(rows)

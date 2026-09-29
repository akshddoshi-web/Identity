"""Edge detection: compares model-implied probability against the de-vigged
CLOSING-line market probability and flags a bet only when the gap exceeds a
configurable threshold.

Why closing line, not opening line, as the comparison point: the closing
line is the market's best, most-information-saturated estimate (it has
absorbed sharp money, injury news, weather, etc.) — it's the standard sharp-
betting benchmark for "how good was this signal, really." If you only have
the line at bet-placement time (not yet closed), edge_detection can run
against that, but the CLV tracker (edge/clv_tracker.py) is what tells you
whether your bet-time edge was real by checking whether the closing line
moved in your favor afterward.

This module does NOT decide whether to bet — it flags a candidate and
attaches the numbers a human (or the Kelly sizer) needs to decide. It is
explicitly not "raw accuracy" driven per the framework's design: a model
that's accurate but never disagrees with the market has zero edge and
should be flagged on nothing.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from edge.devig import DevigResult, devig


@dataclass
class EdgeFlag:
    game_id: str
    market: str                 # spread | total | moneyline
    side: str                    # which side the edge is on
    model_prob: float
    market_prob_devigged: float
    edge: float                   # model_prob - market_prob_devigged
    book: str
    price: float
    flagged: bool


def compute_edge(
    model_prob_side: float,
    price_side: float,
    price_other_side: float,
    devig_method: str = "multiplicative",
) -> tuple[float, DevigResult]:
    """Returns (edge, devig_result) where edge = model_prob_side - devigged
    market prob for that same side. Caller must pass the correct pairing
    (e.g. home price + away price for a moneyline; over price + under price
    for a total)."""
    dv = devig(price_side, price_other_side, method=devig_method)
    market_prob = dv.prob_a
    return model_prob_side - market_prob, dv


def flag_edges(
    candidates: pd.DataFrame,
    min_edge_threshold: float,
    devig_method: str = "multiplicative",
) -> list[EdgeFlag]:
    """candidates columns required: game_id, market, side, model_prob,
    price_side, price_other_side, book.
    """
    flags = []
    required = {"game_id", "market", "side", "model_prob", "price_side", "price_other_side", "book"}
    missing = required - set(candidates.columns)
    if missing:
        raise ValueError(f"candidates frame missing columns: {missing}")

    for _, row in candidates.iterrows():
        edge, dv = compute_edge(row["model_prob"], row["price_side"], row["price_other_side"], devig_method)
        flags.append(
            EdgeFlag(
                game_id=row["game_id"],
                market=row["market"],
                side=row["side"],
                model_prob=float(row["model_prob"]),
                market_prob_devigged=float(dv.prob_a),
                edge=float(edge),
                book=row["book"],
                price=float(row["price_side"]),
                flagged=bool(edge >= min_edge_threshold),
            )
        )
    return flags


def edges_to_frame(flags: list[EdgeFlag]) -> pd.DataFrame:
    return pd.DataFrame([f.__dict__ for f in flags])

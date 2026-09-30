"""Fractional Kelly bet sizing.

Full Kelly maximizes long-run geometric growth in expectation but produces
brutal variance and drawdowns in practice — it assumes your edge estimate is
exactly correct, which it never is (model error, sample noise, injury news
you didn't catch). Sharp bettors near-universally size at a fraction of full
Kelly (commonly 1/4 to 1/2) specifically to control the damage from
overestimated edges. This module implements full Kelly as the mathematical
core, then applies:
  1. A configurable fraction (`kelly_fraction`, default 0.25).
  2. A hard cap as % of bankroll (`max_bet_pct_of_bankroll`, default 0.02),
     which OVERRIDES the fractional-Kelly output if Kelly says to bet more —
     this is a risk-of-ruin backstop independent of how confident the model
     is, because model confidence itself can be wrong.
"""
from __future__ import annotations

from dataclasses import dataclass

from data_pipeline.config import load_config
from edge.devig import american_to_decimal


@dataclass
class KellyResult:
    edge_prob: float             # model_prob - breakeven_prob at this price
    full_kelly_fraction: float    # fraction of bankroll full Kelly says to bet
    fractional_kelly_fraction: float
    capped_fraction: float         # after applying max_bet_pct_of_bankroll
    stake: float
    bankroll: float
    price: float
    was_capped: bool
    negative_ev: bool               # True if model_prob <= breakeven; stake forced to 0


def full_kelly_fraction(model_prob: float, price: float) -> float:
    """f* = (b*p - q) / b, where b = decimal_odds - 1 (net odds), p = model
    win probability, q = 1-p. Returns 0 (never negative) when the bet is -EV
    at this price per the model — Kelly is undefined/nonsensical as a
    negative stake, so we clip at 0 rather than "shorting" a bet, which
    isn't a real action here.
    """
    decimal_odds = american_to_decimal(price)
    b = decimal_odds - 1.0
    q = 1.0 - model_prob
    if b <= 0:
        return 0.0
    f = (b * model_prob - q) / b
    return max(f, 0.0)


def size_bet(
    model_prob: float,
    price: float,
    bankroll: float,
    kelly_fraction: float | None = None,
    max_bet_pct_of_bankroll: float | None = None,
    cfg: dict | None = None,
) -> KellyResult:
    cfg = cfg or load_config()
    kelly_fraction = kelly_fraction if kelly_fraction is not None else cfg["kelly"]["kelly_fraction"]
    max_bet_pct = (
        max_bet_pct_of_bankroll if max_bet_pct_of_bankroll is not None else cfg["kelly"]["max_bet_pct_of_bankroll"]
    )
    min_bankroll_stop = cfg["kelly"].get("min_bankroll_stop", 0.0)

    decimal_odds = american_to_decimal(price)
    breakeven_prob = 1.0 / decimal_odds
    edge_prob = model_prob - breakeven_prob

    f_full = full_kelly_fraction(model_prob, price)
    f_fractional = f_full * kelly_fraction
    negative_ev = f_full <= 0.0

    was_capped = f_fractional > max_bet_pct
    f_capped = min(f_fractional, max_bet_pct)

    if bankroll <= min_bankroll_stop or negative_ev:
        stake = 0.0
        f_capped = 0.0
    else:
        stake = f_capped * bankroll

    return KellyResult(
        edge_prob=edge_prob,
        full_kelly_fraction=f_full,
        fractional_kelly_fraction=f_fractional,
        capped_fraction=f_capped,
        stake=stake,
        bankroll=bankroll,
        price=price,
        was_capped=was_capped,
        negative_ev=negative_ev,
    )

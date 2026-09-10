"""Pure cross-book arbitrage math: implied probability, best-price selection,
and equal-payout stake splitting.

This is price comparison only — no model, no probability estimation, no
opinion on who wins. "Implied probability" here is deliberately the RAW
(vig-included) figure from each book's own price, never de-vigged: true
cross-book arbitrage is about whether the best prices actually available
sum to under 100%, not about what a fair, no-vig market would say.
"""
from __future__ import annotations

from dataclasses import dataclass

from edge.devig import american_to_decimal


@dataclass
class ArbLeg:
    side: str                  # e.g. 'home' | 'away' (or 'over' | 'under' at the call site)
    book: str
    american_odds: float
    decimal_odds: float
    implied_prob: float
    captured_at: str
    stake: float = 0.0
    payout: float = 0.0


@dataclass
class ArbResult:
    legs: list[ArbLeg]
    sum_implied_prob: float
    arb_margin: float           # 1 - sum_implied_prob; > 0 means a real arbitrage
    is_arbitrage: bool


def implied_prob_from_decimal(decimal_odds: float) -> float:
    if decimal_odds <= 1.0:
        raise ValueError(f"decimal odds must be > 1.0, got {decimal_odds}")
    return 1.0 / decimal_odds


def best_leg(side: str, quotes: list[tuple[str, float, str]]) -> ArbLeg | None:
    """quotes: (book, american_odds, captured_at) tuples, all for the SAME
    outcome (e.g. all "home moneyline" quotes across books). Picks the quote
    with the highest decimal odds — the best price available to the bettor
    for that side, regardless of which book offers it. Returns None if
    `quotes` is empty (that side wasn't quoted by any book)."""
    if not quotes:
        return None
    book, price, captured_at = max(quotes, key=lambda q: american_to_decimal(q[1]))
    dec = american_to_decimal(price)
    return ArbLeg(
        side=side, book=book, american_odds=price, decimal_odds=dec,
        implied_prob=implied_prob_from_decimal(dec), captured_at=captured_at,
    )


def evaluate(legs: list[ArbLeg]) -> ArbResult:
    """Sums the best-price legs' raw implied probabilities. `is_arbitrage`
    is True only when that sum is strictly under 1.0 — i.e. there exists a
    stake split that guarantees a profit regardless of outcome."""
    if len(legs) < 2:
        raise ValueError("need at least two sides (legs) to evaluate an arbitrage")
    total = sum(leg.implied_prob for leg in legs)
    margin = 1.0 - total
    return ArbResult(legs=legs, sum_implied_prob=total, arb_margin=margin, is_arbitrage=margin > 0)


def apply_stake_split(result: ArbResult, total_stake: float) -> ArbResult:
    """Splits `total_stake` across each leg proportional to its implied
    probability, so every leg pays out the same amount regardless of which
    outcome happens:

        stake_i = total_stake * (implied_prob_i / sum_implied_prob)
        payout_i = stake_i * decimal_odds_i  ==  total_stake / sum_implied_prob  (constant across legs)

    Mutates each leg's `stake`/`payout` in place and returns the same
    `result` for chaining. Only meaningful when `result.is_arbitrage` is
    True — a non-arbitrage split still balances payouts, but the guaranteed
    "profit" would be negative (a guaranteed loss), so callers should check
    `is_arbitrage` before staking anything.
    """
    if total_stake <= 0:
        raise ValueError("total_stake must be positive")
    for leg in result.legs:
        leg.stake = total_stake * (leg.implied_prob / result.sum_implied_prob)
        leg.payout = leg.stake * leg.decimal_odds
    return result


def guaranteed_profit(result: ArbResult, total_stake: float) -> float:
    """Assumes `apply_stake_split` has already been run on `result`. Every
    leg pays out `total_stake / sum_implied_prob` by construction, so profit
    is that payout minus the total stake — reading it off any single leg is
    enough (they're equal up to floating-point rounding)."""
    return result.legs[0].payout - total_stake

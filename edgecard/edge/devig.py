"""Odds conversion and vig removal.

Sportsbook prices embed a built-in margin (the "vig" or "juice") so that the
implied probabilities of both sides of a market sum to more than 100%. Any
comparison of "model probability vs. market probability" that doesn't strip
this out is comparing against a number that's structurally wrong by
construction — it overstates how much the market actually believes the side
is worse than it is. `devig_two_way` implements the standard multiplicative
(proportional) method; `devig_shin` implements Shin's method, which is more
accurate when there's meaningful favorite-longshot bias (common in NFL/NCAAF
spreads and NBA moneylines on big favorites) at the cost of needing to solve
for a latent insider-trading parameter numerically.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq


def american_to_implied_prob(price: float) -> float:
    """Raw (vig-included) implied probability from an American odds price."""
    if price > 0:
        return 100.0 / (price + 100.0)
    else:
        return -price / (-price + 100.0)


def american_to_decimal(price: float) -> float:
    if price > 0:
        return 1.0 + price / 100.0
    else:
        return 1.0 + 100.0 / (-price)


def decimal_to_american(dec: float) -> float:
    if dec >= 2.0:
        return (dec - 1.0) * 100.0
    else:
        return -100.0 / (dec - 1.0)


@dataclass
class DevigResult:
    prob_a: float
    prob_b: float
    overround: float          # raw vig-included sum minus 1.0
    method: str


def devig_two_way(price_a: float, price_b: float) -> DevigResult:
    """Proportional (multiplicative) de-vig: scales both raw implied
    probabilities down by the same factor so they sum to 1. Simple, standard,
    and the right default when you don't have strong reason to believe in
    asymmetric favorite-longshot bias for this market."""
    p_a_raw = american_to_implied_prob(price_a)
    p_b_raw = american_to_implied_prob(price_b)
    overround = p_a_raw + p_b_raw - 1.0
    total = p_a_raw + p_b_raw
    return DevigResult(prob_a=p_a_raw / total, prob_b=p_b_raw / total, overround=overround, method="multiplicative")


def devig_shin(price_a: float, price_b: float) -> DevigResult:
    """Shin's (1992) method: models the overround as arising partly from
    informed ("insider") money, solving for a latent parameter z such that

        p_i = ( sqrt(z^2 + 4*(1-z)*pi_i^2 / S) - z ) / (2*(1-z))

    where pi_i are raw implied probabilities and S = sum(pi_i). Tends to
    correct favorite-longshot bias better than the proportional method on
    two-way markets with a big favorite. Falls back to the proportional
    method if the solver fails to converge (rare, but a wide two-way market
    with an extreme overround can push z outside a sane bracket).
    """
    p_a_raw = american_to_implied_prob(price_a)
    p_b_raw = american_to_implied_prob(price_b)
    overround = p_a_raw + p_b_raw - 1.0
    S = p_a_raw + p_b_raw

    def _shin_prob(pi: float, z: float) -> float:
        return (np.sqrt(z ** 2 + 4 * (1 - z) * pi ** 2 / S) - z) / (2 * (1 - z))

    def f(z: float) -> float:
        return _shin_prob(p_a_raw, z) + _shin_prob(p_b_raw, z) - 1.0

    try:
        z = brentq(f, 1e-6, 0.2)
        prob_a = _shin_prob(p_a_raw, z)
        prob_b = _shin_prob(p_b_raw, z)
        return DevigResult(prob_a=prob_a, prob_b=prob_b, overround=overround, method="shin")
    except (ValueError, ZeroDivisionError):
        return devig_two_way(price_a, price_b)


def devig(price_a: float, price_b: float, method: str = "multiplicative") -> DevigResult:
    if method == "shin":
        return devig_shin(price_a, price_b)
    return devig_two_way(price_a, price_b)

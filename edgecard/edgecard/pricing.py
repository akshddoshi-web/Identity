"""Small pricing helpers shared by the card builder, tracking, and tests."""
from __future__ import annotations

import numpy as np

from edge.devig import american_to_decimal, american_to_implied_prob, decimal_to_american, devig_two_way


def novig_two_way(price_a: float, price_b: float) -> tuple[float, float]:
    r = devig_two_way(price_a, price_b)
    return r.prob_a, r.prob_b


def fair_from_books(books: dict[str, tuple[float, float]]) -> float:
    """Consensus no-vig probability of side A: the MEDIAN across books of
    each book's own two-way no-vig probability. The median (not the best
    price) is the fair-value anchor — the best price is what we bet into."""
    probs = [devig_two_way(a, b).prob_a for a, b in books.values() if a and b]
    return float(np.median(probs)) if probs else float("nan")


def ev_per_100(p_win: float, price: float, p_push: float = 0.0) -> float:
    """Expected profit per $100 staked. Pushes return the stake."""
    win_amt = (american_to_decimal(price) - 1) * 100
    p_lose = max(0.0, 1 - p_win - p_push)
    return p_win * win_amt - p_lose * 100


def breakeven_price(p_win: float, min_edge: float = 0.0, p_push: float = 0.0) -> float:
    """Worst American price at which the bet still has at least `min_edge`
    expected return per unit staked. With min_edge=0 this is the fair price.
    Solves p*(d-1) - (1-p-push) = min_edge for decimal odds d."""
    p_lose = max(1e-9, 1 - p_win - p_push)
    if p_win <= 0:
        return float("inf")
    d = 1 + (min_edge + p_lose) / p_win
    return float(decimal_to_american(d))


def parlay_decimal(prices: list[float]) -> float:
    out = 1.0
    for p in prices:
        out *= american_to_decimal(p)
    return out


def implied(price: float) -> float:
    return american_to_implied_prob(price)

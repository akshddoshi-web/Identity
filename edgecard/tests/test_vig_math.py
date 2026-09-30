"""Vig-removal and pricing math, checked against hand-computed values."""
from __future__ import annotations

import math

import numpy as np
import pytest

from edge.devig import american_to_decimal, american_to_implied_prob, decimal_to_american, devig_shin, devig_two_way
from edgecard.odds import kalshi_fee_adjusted_american
from edgecard.pricing import breakeven_price, ev_per_100, fair_from_books, novig_two_way, parlay_decimal
from models.distributions import DiscreteDist, KeyWeights, MARGIN_SUPPORT, moneyline_prob, spread_prob, total_prob
from models.game_model import fit_model_weight


def test_implied_probability_examples():
    assert american_to_implied_prob(-110) == pytest.approx(110 / 210)
    assert american_to_implied_prob(+150) == pytest.approx(0.4)
    assert american_to_implied_prob(-200) == pytest.approx(2 / 3)
    assert american_to_implied_prob(+100) == pytest.approx(0.5)


def test_standard_juice_devigs_to_even():
    r = devig_two_way(-110, -110)
    assert r.prob_a == pytest.approx(0.5)
    assert r.overround == pytest.approx(2 * 110 / 210 - 1)  # 4.76%


def test_devig_hand_example():
    # -150 / +130: raw 0.6 and 0.434783; sum 1.034783
    r = devig_two_way(-150, 130)
    assert r.prob_a == pytest.approx(0.6 / (0.6 + 100 / 230), rel=1e-9)
    assert r.prob_a + r.prob_b == pytest.approx(1.0)
    assert r.prob_a == pytest.approx(0.57983, abs=1e-5)


def test_shin_sums_to_one_and_shades_longshot():
    r = devig_shin(-400, 320)
    m = devig_two_way(-400, 320)
    assert r.prob_a + r.prob_b == pytest.approx(1.0, abs=1e-9)
    assert r.prob_b < m.prob_b  # Shin removes more margin from the longshot


def test_novig_two_way_matches_devig():
    a, b = novig_two_way(-125, 105)
    r = devig_two_way(-125, 105)
    assert a == pytest.approx(r.prob_a) and b == pytest.approx(r.prob_b)


@pytest.mark.parametrize("price", [-500, -200, -110, 100, 120, 250, 1000])
def test_american_decimal_round_trip(price):
    assert decimal_to_american(american_to_decimal(price)) == pytest.approx(price)


def test_ev_per_100():
    # fair coin at +110: EV = 0.5*110 - 0.5*100 = +5
    assert ev_per_100(0.5, 110) == pytest.approx(5.0)
    assert ev_per_100(0.5, -110) == pytest.approx(0.5 * 100 * 100 / 110 - 50)
    # pushes return the stake: 45% win, 10% push, 45% lose at -110 -> EV = 0.45*90.909 - 45
    assert ev_per_100(0.45, -110, p_push=0.10) == pytest.approx(0.45 * 100 * 100 / 110 - 45)


def test_breakeven_price():
    assert breakeven_price(0.5) == pytest.approx(100.0)
    assert breakeven_price(0.5, min_edge=0.0) == pytest.approx(100.0)
    p = 0.55
    be = breakeven_price(p)
    assert american_to_implied_prob(be) == pytest.approx(p)


def test_fair_from_books_uses_consensus_not_best():
    books = {"a": (-110, -110), "b": (-105, -115), "c": (-120, 100)}
    fair = fair_from_books(books)
    assert 0.45 < fair < 0.56
    manual = np.median([devig_two_way(*v).prob_a for v in books.values()])
    assert fair == pytest.approx(manual)


def test_parlay_decimal():
    assert parlay_decimal([-110, -110]) == pytest.approx((1 + 100 / 110) ** 2)


def test_kalshi_fee_makes_price_worse_than_raw():
    raw = 0.58
    price = kalshi_fee_adjusted_american(raw)
    assert american_to_implied_prob(price) > raw  # fee raises the effective cost


def test_distribution_probabilities_are_consistent():
    kw = KeyWeights.flat(MARGIN_SUPPORT)
    d = DiscreteDist.build(3.0, 13.5, kw)
    assert d.pmf.sum() == pytest.approx(1.0)
    ml_h, ml_a = moneyline_prob(d, "home"), moneyline_prob(d, "away")
    assert ml_h.win + ml_h.push + ml_h.lose == pytest.approx(1.0)
    assert ml_h.win == pytest.approx(ml_a.lose)
    # home -3 pushes exactly at margin 3; home -3.5 never pushes
    assert spread_prob(d, -3.0, "home").push == pytest.approx(d.prob_equal(3))
    assert spread_prob(d, -3.5, "home").push == 0.0
    # home -3.5 and away +3.5 are complements
    assert spread_prob(d, -3.5, "home").win + spread_prob(d, 3.5, "away").win == pytest.approx(1.0)
    t = DiscreteDist.build(44.0, 13.0, KeyWeights.flat(np.arange(0, 181)))
    assert total_prob(t, 44.5, "over").win + total_prob(t, 44.5, "under").win == pytest.approx(1.0)


def test_key_number_weights_put_mass_on_three():
    rng = np.random.default_rng(0)
    base = rng.normal(2, 13, 20000).round()
    threes = np.full(3000, 3.0)
    kw = KeyWeights.fit(np.concatenate([base, threes]), MARGIN_SUPPORT)
    i3, i4 = list(MARGIN_SUPPORT).index(3), list(MARGIN_SUPPORT).index(4)
    assert kw.weights[i3] > 1.5 * kw.weights[i4]


def test_model_weight_is_zero_without_information():
    """A model that is the market plus noise must (almost always) get w = 0."""
    false_pos = 0
    for seed in range(20):
        rng = np.random.default_rng(seed)
        mkt = rng.uniform(0.3, 0.7, 3000)
        y = (rng.uniform(size=3000) < mkt).astype(float)
        noise_model = np.clip(mkt + rng.normal(0, 0.08, 3000), 0.02, 0.98)
        false_pos += fit_model_weight(noise_model, mkt, y)["w"] > 0
    assert false_pos <= 1


def test_model_weight_detects_real_information():
    rng = np.random.default_rng(2)
    truth = rng.uniform(0.25, 0.75, 6000)
    y = (rng.uniform(size=6000) < truth).astype(float)
    mkt = np.clip(truth + rng.normal(0, 0.06, 6000), 0.05, 0.95)  # market is noisy
    model = truth                                                # model knows the truth
    r = fit_model_weight(model, mkt, y)
    assert r["significant"] and r["w"] > 0.3

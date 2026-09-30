import math

import pytest

from edge.devig import (
    american_to_implied_prob,
    american_to_decimal,
    decimal_to_american,
    devig_two_way,
    devig_shin,
)


def test_american_to_implied_prob_favorite():
    assert american_to_implied_prob(-110) == pytest.approx(110 / 210)


def test_american_to_implied_prob_underdog():
    assert american_to_implied_prob(150) == pytest.approx(100 / 250)


def test_decimal_roundtrip_favorite():
    dec = american_to_decimal(-150)
    assert dec == pytest.approx(1 + 100 / 150)
    assert decimal_to_american(dec) == pytest.approx(-150)


def test_decimal_roundtrip_underdog():
    dec = american_to_decimal(120)
    assert dec == pytest.approx(2.2)
    assert decimal_to_american(dec) == pytest.approx(120)


def test_devig_two_way_sums_to_one():
    result = devig_two_way(-110, -110)
    assert result.prob_a + result.prob_b == pytest.approx(1.0)
    assert result.prob_a == pytest.approx(0.5)
    assert result.overround > 0


def test_devig_two_way_asymmetric():
    result = devig_two_way(-150, 130)
    assert result.prob_a + result.prob_b == pytest.approx(1.0)
    assert result.prob_a > result.prob_b  # favorite retains higher prob after devig


def test_devig_shin_sums_to_one():
    result = devig_shin(-150, 130)
    assert result.prob_a + result.prob_b == pytest.approx(1.0, abs=1e-4)


def test_devig_shin_falls_back_gracefully():
    # extreme mismatched prices shouldn't crash — either converges or falls back
    result = devig_shin(-10000, 5000)
    assert 0.0 <= result.prob_a <= 1.0
    assert result.prob_a + result.prob_b == pytest.approx(1.0, abs=1e-3)


def test_no_vig_market_devig_is_noop():
    # a hypothetical fair two-way market (no overround) devigs to itself
    result = devig_two_way(100, -100)
    assert result.prob_a == pytest.approx(0.5)
    assert result.overround == pytest.approx(0.0)

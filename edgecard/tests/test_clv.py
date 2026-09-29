import numpy as np
import pytest

from edge.clv_tracker import summarize_clv, compute_clv_for_bet, american_implied


def _cfg(min_n=200, confidence=0.95):
    return {"edge_detection": {"min_sample_size_for_significance": min_n, "confidence_level": confidence}}


def test_small_sample_flagged_not_significant():
    values = np.random.default_rng(0).normal(0.02, 0.01, 50)
    summary = summarize_clv(values, _cfg())
    assert summary.n == 50
    assert summary.is_significant_sample is False


def test_large_sample_flagged_significant():
    values = np.random.default_rng(0).normal(0.02, 0.01, 250)
    summary = summarize_clv(values, _cfg())
    assert summary.n == 250
    assert summary.is_significant_sample is True


def test_empty_sample_handled():
    summary = summarize_clv(np.array([]), _cfg())
    assert summary.n == 0
    assert summary.is_significant_sample is False


def test_compute_clv_for_bet_positive_when_line_moves_in_bettors_favor():
    # bettor got -110 (implied ~52.4%); closing line implies the side is now
    # a bigger favorite (e.g. -130 vs +110 other side) -> positive CLV
    clv = compute_clv_for_bet(bet_price=-110, closing_price_side=-130, closing_price_other_side=110)
    assert clv > 0


def test_compute_clv_for_bet_negative_when_line_moves_against_bettor():
    clv = compute_clv_for_bet(bet_price=-130, closing_price_side=-110, closing_price_other_side=-110)
    assert clv < 0


def test_american_implied_matches_manual_calc():
    assert american_implied(-110) == pytest.approx(110 / 210)
    assert american_implied(150) == pytest.approx(100 / 250)

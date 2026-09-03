import pytest

from bankroll.kelly import full_kelly_fraction, size_bet


def test_full_kelly_zero_at_breakeven():
    # at -110, breakeven prob is 110/210 ~ 0.5238; exactly at breakeven, f* = 0
    f = full_kelly_fraction(110 / 210, -110)
    assert f == pytest.approx(0.0, abs=1e-6)


def test_full_kelly_positive_with_edge():
    f = full_kelly_fraction(0.60, -110)
    assert f > 0


def test_full_kelly_clips_negative_to_zero():
    f = full_kelly_fraction(0.40, -110)
    assert f == 0.0


def test_size_bet_applies_fraction_and_cap():
    cfg = {
        "kelly": {"kelly_fraction": 0.5, "max_bet_pct_of_bankroll": 0.02, "min_bankroll_stop": 0.0},
    }
    result = size_bet(model_prob=0.65, price=-110, bankroll=10_000, cfg=cfg)
    full = full_kelly_fraction(0.65, -110)
    assert result.full_kelly_fraction == pytest.approx(full)
    assert result.fractional_kelly_fraction == pytest.approx(full * 0.5)
    # half-Kelly at 65% on -110 is large enough that the 2% cap should bind
    assert result.was_capped is True
    assert result.capped_fraction == pytest.approx(0.02)
    assert result.stake == pytest.approx(200.0)


def test_size_bet_negative_ev_returns_zero_stake():
    cfg = {"kelly": {"kelly_fraction": 0.25, "max_bet_pct_of_bankroll": 0.02, "min_bankroll_stop": 0.0}}
    result = size_bet(model_prob=0.45, price=-110, bankroll=10_000, cfg=cfg)
    assert result.negative_ev is True
    assert result.stake == 0.0


def test_size_bet_respects_min_bankroll_stop():
    cfg = {"kelly": {"kelly_fraction": 0.25, "max_bet_pct_of_bankroll": 0.02, "min_bankroll_stop": 100.0}}
    result = size_bet(model_prob=0.65, price=-110, bankroll=50, cfg=cfg)
    assert result.stake == 0.0


def test_size_bet_small_edge_not_capped():
    cfg = {"kelly": {"kelly_fraction": 0.25, "max_bet_pct_of_bankroll": 0.10, "min_bankroll_stop": 0.0}}
    result = size_bet(model_prob=0.55, price=-110, bankroll=10_000, cfg=cfg)
    assert result.was_capped is False
    assert result.stake == pytest.approx(result.capped_fraction * 10_000)

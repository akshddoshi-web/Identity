import pytest

from arbitrage.arb_math import (
    implied_prob_from_decimal,
    best_leg,
    evaluate,
    apply_stake_split,
    guaranteed_profit,
)
from arbitrage.arb_scanner import scan_game, opportunities_to_frame, OUTPUT_COLUMNS
from data_pipeline.schema import OddsSnapshot


# --------------------------------------------------------------------------- #
# arb_math
# --------------------------------------------------------------------------- #


def test_implied_prob_from_decimal():
    assert implied_prob_from_decimal(2.0) == pytest.approx(0.5)
    assert implied_prob_from_decimal(1.5) == pytest.approx(2 / 3)


def test_implied_prob_rejects_invalid_decimal_odds():
    with pytest.raises(ValueError):
        implied_prob_from_decimal(1.0)


def test_best_leg_picks_highest_decimal_odds_across_books():
    # -110 (dec 1.909) vs. +105 (dec 2.05) vs. -120 (dec 1.833): +105 is best for the bettor.
    quotes = [("bookA", -110, "t0"), ("bookB", 105, "t0"), ("bookC", -120, "t0")]
    leg = best_leg("home", quotes)
    assert leg.book == "bookB"
    assert leg.american_odds == 105


def test_best_leg_empty_returns_none():
    assert best_leg("home", []) is None


def test_evaluate_detects_true_arbitrage():
    # Two books each paying +150 (dec 2.5, implied 0.4) on opposite sides
    # of a two-way market: 0.4 + 0.4 = 0.8 < 1.0 -> guaranteed edge.
    home = best_leg("home", [("bookA", 150, "t0")])
    away = best_leg("away", [("bookB", 150, "t0")])
    result = evaluate([home, away])
    assert result.sum_implied_prob == pytest.approx(0.8)
    assert result.arb_margin == pytest.approx(0.2)
    assert result.is_arbitrage is True


def test_evaluate_no_arbitrage_on_vigged_market():
    # Standard -110/-110 market: implied probs sum well over 1.0 (the vig).
    home = best_leg("home", [("bookA", -110, "t0")])
    away = best_leg("away", [("bookB", -110, "t0")])
    result = evaluate([home, away])
    assert result.sum_implied_prob > 1.0
    assert result.is_arbitrage is False


def test_evaluate_requires_at_least_two_legs():
    home = best_leg("home", [("bookA", 150, "t0")])
    with pytest.raises(ValueError):
        evaluate([home])


def test_stake_split_produces_equal_payouts_and_full_allocation():
    home = best_leg("home", [("bookA", 150, "t0")])
    away = best_leg("away", [("bookB", 150, "t0")])
    result = evaluate([home, away])
    apply_stake_split(result, total_stake=1000.0)

    payouts = [leg.payout for leg in result.legs]
    assert payouts[0] == pytest.approx(payouts[1])
    assert sum(leg.stake for leg in result.legs) == pytest.approx(1000.0)


def test_guaranteed_profit_matches_closed_form():
    home = best_leg("home", [("bookA", 150, "t0")])
    away = best_leg("away", [("bookB", 150, "t0")])
    result = evaluate([home, away])
    apply_stake_split(result, total_stake=1000.0)
    profit = guaranteed_profit(result, total_stake=1000.0)

    # payout_i = total_stake / sum_implied_prob (constant across legs), so
    # profit = total_stake * (1 - sum_implied_prob) / sum_implied_prob
    #        = total_stake * arb_margin / sum_implied_prob
    expected = 1000.0 * result.arb_margin / result.sum_implied_prob
    assert profit == pytest.approx(expected)
    assert profit == pytest.approx(250.0)  # 1000/0.8 - 1000


def test_apply_stake_split_rejects_nonpositive_stake():
    home = best_leg("home", [("bookA", 150, "t0")])
    away = best_leg("away", [("bookB", 150, "t0")])
    result = evaluate([home, away])
    with pytest.raises(ValueError):
        apply_stake_split(result, total_stake=0.0)


# --------------------------------------------------------------------------- #
# arb_scanner
# --------------------------------------------------------------------------- #


def _snap(book, market, home_price, away_price, captured_at="2026-09-10T18:00:00", home_point=None, away_point=None):
    return OddsSnapshot(
        game_id="G1", book=book, snapshot_type="live", captured_at=captured_at, market=market,
        home_price=home_price, away_price=away_price, home_point=home_point, away_point=away_point,
    )


def test_scan_game_finds_moneyline_arbitrage_across_books():
    snapshots = [
        _snap("bookA", "moneyline", home_price=150, away_price=-140),
        _snap("bookB", "moneyline", home_price=-130, away_price=150),
    ]
    # Best home price is bookA's +150 (implied 0.4); best away price is bookB's +150 (implied 0.4).
    opps = scan_game(snapshots, "NFL", "G1", "Home Team", "Away Team", total_stake=1000.0, markets=("moneyline",))
    assert len(opps) == 1
    opp = opps[0]
    assert opp.arb_margin == pytest.approx(0.2)
    assert {leg.book for leg in opp.legs} == {"bookA", "bookB"}


def test_scan_game_no_arbitrage_returns_empty_list():
    snapshots = [
        _snap("bookA", "moneyline", home_price=-110, away_price=-110),
        _snap("bookB", "moneyline", home_price=-115, away_price=-105),
    ]
    opps = scan_game(snapshots, "NFL", "G1", "Home Team", "Away Team", total_stake=1000.0, markets=("moneyline",))
    assert opps == []


def test_scan_game_spread_requires_matching_line():
    # bookA quotes home at -3, bookB quotes home at -3.5 -- different lines,
    # so they must NOT be pooled together into one (mismatched, non-riskless)
    # arb. Each book's own two sides carry ordinary vig (sum > 1) on their
    # own line, so no real arbitrage exists at either line in isolation.
    snapshots = [
        _snap("bookA", "spread", home_price=-110, away_price=-110, home_point=-3.0, away_point=3.0),
        _snap("bookB", "spread", home_price=-105, away_price=-115, home_point=-3.5, away_point=3.5),
    ]
    opps = scan_game(snapshots, "NFL", "G1", "Home Team", "Away Team", total_stake=1000.0, markets=("spread",))
    # Each line only has one book quoting it, so pairing within a line just
    # reproduces that single book's own vigged market -- no cross-book gap.
    assert opps == []


def test_scan_game_spread_arbitrage_at_matching_line():
    snapshots = [
        _snap("bookA", "spread", home_price=150, away_price=-140, home_point=-3.0, away_point=3.0),
        _snap("bookB", "spread", home_price=-130, away_price=150, home_point=-3.0, away_point=3.0),
    ]
    opps = scan_game(snapshots, "NFL", "G1", "Home Team", "Away Team", total_stake=1000.0, markets=("spread",))
    assert len(opps) == 1
    assert opps[0].line == pytest.approx(-3.0)


def test_scan_game_total_labels_over_under_correctly():
    snapshots = [
        _snap("bookA", "total", home_price=150, away_price=-140, home_point=47.5, away_point=47.5),
        _snap("bookB", "total", home_price=-130, away_price=150, home_point=47.5, away_point=47.5),
    ]
    opps = scan_game(snapshots, "NFL", "G1", "Home Team", "Away Team", total_stake=1000.0, markets=("total",))
    assert len(opps) == 1
    df = opportunities_to_frame(opps)
    assert set(df.loc[0, ["side_a", "side_b"]]) == {"over", "under"}


def test_freshness_flag_set_when_pull_gap_exceeds_threshold():
    snapshots = [
        _snap("bookA", "moneyline", home_price=150, away_price=-140, captured_at="2026-09-10T18:00:00"),
        _snap("bookB", "moneyline", home_price=-130, away_price=150, captured_at="2026-09-10T18:05:00"),
    ]
    opps = scan_game(
        snapshots, "NFL", "G1", "Home Team", "Away Team", total_stake=1000.0,
        staleness_threshold_seconds=60.0, markets=("moneyline",),
    )
    assert len(opps) == 1
    assert opps[0].max_pull_gap_seconds == pytest.approx(300.0)
    assert opps[0].is_stale is True


def test_freshness_flag_not_set_within_threshold():
    snapshots = [
        _snap("bookA", "moneyline", home_price=150, away_price=-140, captured_at="2026-09-10T18:00:00"),
        _snap("bookB", "moneyline", home_price=-130, away_price=150, captured_at="2026-09-10T18:00:30"),
    ]
    opps = scan_game(
        snapshots, "NFL", "G1", "Home Team", "Away Team", total_stake=1000.0,
        staleness_threshold_seconds=60.0, markets=("moneyline",),
    )
    assert opps[0].is_stale is False


def test_opportunities_to_frame_empty_has_expected_columns():
    df = opportunities_to_frame([])
    assert df.empty
    assert list(df.columns) == OUTPUT_COLUMNS


def test_opportunities_to_frame_sorted_by_margin_descending():
    big_margin = [
        _snap("bookA", "moneyline", home_price=200, away_price=-140),
        _snap("bookB", "moneyline", home_price=-130, away_price=200),
    ]
    small_margin_snaps = [
        _snap("bookC", "moneyline", home_price=105, away_price=-140, captured_at="2026-09-10T18:00:00"),
        _snap("bookD", "moneyline", home_price=-130, away_price=105, captured_at="2026-09-10T18:00:00"),
    ]
    opps = scan_game(big_margin, "NFL", "G1", "H", "A", total_stake=1000.0, markets=("moneyline",))
    opps += scan_game(small_margin_snaps, "NFL", "G2", "H2", "A2", total_stake=1000.0, markets=("moneyline",))
    df = opportunities_to_frame(opps)
    assert df["arb_margin_pct"].is_monotonic_decreasing

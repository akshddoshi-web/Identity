import datetime as dt

import pytest

from data_pipeline.schema import OddsSnapshot
from scripts.daily_report import (
    pick_preferred_snapshot,
    evaluate_game_edges,
    format_market_line,
    format_model_line,
    _rest_days,
    _last_game_dates,
)
import pandas as pd


def _snap(book, market, **kwargs):
    return OddsSnapshot(game_id="g1", book=book, snapshot_type="live", captured_at="2024-01-01T00:00:00Z", market=market, **kwargs)


def test_pick_preferred_snapshot_prefers_configured_order():
    snapshots = [
        _snap("draftkings", "moneyline", home_price=-120, away_price=100),
        _snap("pinnacle", "moneyline", home_price=-115, away_price=105),
    ]
    picked = pick_preferred_snapshot(snapshots, "moneyline", ["pinnacle", "draftkings"])
    assert picked.book == "pinnacle"


def test_pick_preferred_snapshot_falls_back_when_preferred_absent():
    snapshots = [_snap("fanduel", "moneyline", home_price=-120, away_price=100)]
    picked = pick_preferred_snapshot(snapshots, "moneyline", ["pinnacle", "draftkings"])
    assert picked.book == "fanduel"


def test_pick_preferred_snapshot_returns_none_for_missing_market():
    snapshots = [_snap("pinnacle", "moneyline", home_price=-120, away_price=100)]
    assert pick_preferred_snapshot(snapshots, "spread", ["pinnacle"]) is None


def test_evaluate_game_edges_flags_home_moneyline_when_model_disagrees():
    snapshots = [_snap("pinnacle", "moneyline", home_price=-110, away_price=-110)]  # devigged ~50/50
    flags = evaluate_game_edges(
        sport="NFL", game_id="g1", home_team="A", away_team="B", commence_time="2024-01-01T18:00:00Z",
        model_prob_home=0.60, model_margin=3.0, model_total=44.0,
        snapshots=snapshots, sigma_margin=13.0, sigma_total=10.0, min_edge=0.03,
        preferred_books=["pinnacle"],
    )
    assert len(flags) == 1
    assert flags[0]["market"] == "moneyline"
    assert flags[0]["side"] == "home"
    assert flags[0]["edge"] == pytest.approx(0.10, abs=1e-6)


def test_evaluate_game_edges_flags_away_when_model_favors_away():
    snapshots = [_snap("pinnacle", "moneyline", home_price=-110, away_price=-110)]
    flags = evaluate_game_edges(
        sport="NFL", game_id="g1", home_team="A", away_team="B", commence_time="2024-01-01T18:00:00Z",
        model_prob_home=0.40, model_margin=-3.0, model_total=44.0,
        snapshots=snapshots, sigma_margin=13.0, sigma_total=10.0, min_edge=0.03,
        preferred_books=["pinnacle"],
    )
    ml_flags = [f for f in flags if f["market"] == "moneyline"]
    assert len(ml_flags) == 1
    assert ml_flags[0]["side"] == "away"


def test_evaluate_game_edges_no_flag_when_under_threshold():
    snapshots = [_snap("pinnacle", "moneyline", home_price=-110, away_price=-110)]
    flags = evaluate_game_edges(
        sport="NFL", game_id="g1", home_team="A", away_team="B", commence_time="2024-01-01T18:00:00Z",
        model_prob_home=0.51, model_margin=0.5, model_total=44.0,
        snapshots=snapshots, sigma_margin=13.0, sigma_total=10.0, min_edge=0.03,
        preferred_books=["pinnacle"],
    )
    assert flags == []


def test_evaluate_game_edges_spread_and_total_independent_of_moneyline():
    snapshots = [
        _snap("pinnacle", "moneyline", home_price=-110, away_price=-110),
        _snap("pinnacle", "spread", home_price=-110, away_price=-110, home_point=-3.0, away_point=3.0),
        _snap("pinnacle", "total", home_price=-110, away_price=-110, home_point=44.0, away_point=44.0),
    ]
    # model predicts home wins by a lot more than the spread implies, and a
    # much higher total than the market -> both spread and total should flag
    flags = evaluate_game_edges(
        sport="NFL", game_id="g1", home_team="A", away_team="B", commence_time="2024-01-01T18:00:00Z",
        model_prob_home=0.50, model_margin=12.0, model_total=58.0,
        snapshots=snapshots, sigma_margin=13.0, sigma_total=10.0, min_edge=0.03,
        preferred_books=["pinnacle"],
    )
    markets_flagged = {f["market"] for f in flags}
    assert "spread" in markets_flagged
    assert "total" in markets_flagged
    assert "moneyline" not in markets_flagged  # model_prob_home == breakeven exactly


def test_format_market_line_variants():
    assert format_market_line("moneyline", "home", -150, None) == "Home -150"
    assert format_market_line("spread", "away", -110, 6.5) == "Away +6.5 (-110)"
    assert format_market_line("total", "over", -105, 47.5) == "Over 47.5 (-105)"


def test_format_model_line_variants():
    assert "win prob" in format_model_line("moneyline", "home", 0.612, 0, 0)
    assert "cover prob" in format_model_line("spread", "home", 0.55, 3.2, 0)
    assert "under prob" in format_model_line("total", "under", 0.51, 0, 41.0)


def test_rest_days_computes_positive_gap():
    assert _rest_days("2024-01-01", "2024-01-08T18:00:00Z") == 7


def test_rest_days_none_when_no_prior_game():
    assert _rest_days(None, "2024-01-08T18:00:00Z") is None


def test_last_game_dates_takes_most_recent():
    games = pd.DataFrame(
        [
            {"home_team": "A", "away_team": "B", "game_date": "2024-01-01"},
            {"home_team": "B", "away_team": "A", "game_date": "2024-01-10"},
        ]
    )
    last = _last_game_dates(games)
    assert last["A"] == "2024-01-10"
    assert last["B"] == "2024-01-10"

import numpy as np
import pandas as pd
import pytest

from models.features import select_populated_feature_columns, build_live_feature_rows


def test_select_populated_feature_columns_drops_mostly_null():
    df = pd.DataFrame({"good": [1, 2, 3, 4], "bad": [None, None, None, 1]})
    result = select_populated_feature_columns(df, ["good", "bad"], min_frac=0.5)
    assert result == ["good"]


def test_select_populated_feature_columns_keeps_fully_populated():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0]})
    result = select_populated_feature_columns(df, ["a", "b"], min_frac=0.5)
    assert set(result) == {"a", "b"}


def _hist_games(n_games=6):
    """Team A plays home every game, alternating opponents, epa climbing
    steadily so the rolling average is easy to predict by hand."""
    rows = []
    for i in range(n_games):
        rows.append(
            {
                "game_id": f"g{i}",
                "sport": "NFL",
                "season": 2023,
                "week": i + 1,
                "game_date": f"2023-09-{i + 1:02d}",
                "home_team": "A",
                "away_team": "B",
                "home_score": 24,
                "away_score": 17,
                "is_final": 1,
                "neutral_site": 0,
                "home_rest_days": 7,
                "away_rest_days": 7,
                "home_travel_mi": 0.0,
                "away_travel_mi": 500.0,
                "referee_crew": None,
                "weather_temp_f": 60.0,
                "weather_wind_mph": 5.0,
                "weather_precip": "none",
                "is_dome": 0,
            }
        )
    return pd.DataFrame(rows)


def _hist_stats(n_games=6):
    rows = []
    for i in range(n_games):
        # Team A's epa_per_play increases by 0.1 each game: 0.0, 0.1, 0.2, ...
        rows.append({"game_id": f"g{i}", "team": "A", "is_home": 1, "epa_per_play": round(i * 0.1, 2)})
        rows.append({"game_id": f"g{i}", "team": "B", "is_home": 0, "epa_per_play": 0.0})
    return pd.DataFrame(rows)


def test_build_live_feature_rows_uses_trailing_form_not_todays_placeholder():
    games_hist = _hist_games(6)
    stats_hist = _hist_stats(6)
    games_today = pd.DataFrame(
        [
            {
                "game_id": "g_today",
                "sport": "NFL",
                "season": 2023,
                "week": 7,
                "game_date": "2023-09-20",
                "home_team": "A",
                "away_team": "B",
                "home_score": None,
                "away_score": None,
                "is_final": 0,
                "neutral_site": 0,
                "home_rest_days": None,
                "away_rest_days": None,
                "home_travel_mi": None,
                "away_travel_mi": None,
                "referee_crew": None,
                "weather_temp_f": None,
                "weather_wind_mph": None,
                "weather_precip": None,
                "is_dome": 0,
            }
        ]
    )
    elo_ratings = {"A": 1550.0, "B": 1480.0}

    live = build_live_feature_rows(games_hist, stats_hist, games_today, "NFL", elo_ratings, rolling_window=8)

    assert len(live) == 1
    row = live.iloc[0]
    # trailing average of A's epa_per_play over games 0..5 (0.0..0.5) = 0.25
    assert row["home_epa_per_play_roll"] == pytest.approx(0.25)
    assert row["away_epa_per_play_roll"] == pytest.approx(0.0)
    assert row["home_elo_pre"] == pytest.approx(1550.0)
    assert row["away_elo_pre"] == pytest.approx(1480.0)
    assert row["elo_diff"] == pytest.approx(70.0)


def test_build_live_feature_rows_no_object_dtype_columns():
    # regression test: None-valued live columns must not surface as
    # pandas 'object' dtype after concatenation with historical float columns
    # (XGBoost predict rejects object dtype outright).
    games_hist = _hist_games(6)
    stats_hist = _hist_stats(6)
    games_today = pd.DataFrame(
        [
            {
                "game_id": "g_today",
                "sport": "NFL",
                "season": 2023,
                "week": 7,
                "game_date": "2023-09-20",
                "home_team": "A",
                "away_team": "B",
                "home_score": None,
                "away_score": None,
                "is_final": 0,
                "neutral_site": 0,
                "home_rest_days": None,
                "away_rest_days": None,
                "home_travel_mi": None,
                "away_travel_mi": None,
                "referee_crew": None,
                "weather_temp_f": None,
                "weather_wind_mph": None,
                "weather_precip": None,
                "is_dome": 0,
            }
        ]
    )
    live = build_live_feature_rows(games_hist, stats_hist, games_today, "NFL", {}, rolling_window=8)
    numeric_cols = [c for c in live.columns if c.endswith("_roll") or c in ("home_travel_mi", "away_travel_mi", "weather_temp_f")]
    for c in numeric_cols:
        assert live[c].dtype.kind in "biuf", f"{c} has dtype {live[c].dtype}, expected numeric"

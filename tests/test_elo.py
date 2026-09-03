import pytest

from models.elo import EloModel, DEFAULT_RATING


def test_initial_rating_is_default():
    model = EloModel()
    assert model.get_rating("Team A") == DEFAULT_RATING


def test_win_probability_home_favored_with_home_advantage():
    model = EloModel(home_advantage=55.0)
    prob = model.win_probability("Home", "Away")
    assert prob > 0.5  # equal ratings but home advantage tips it


def test_win_probability_neutral_site_removes_advantage():
    model = EloModel(home_advantage=55.0)
    prob = model.win_probability("Home", "Away", neutral_site=True)
    assert prob == pytest.approx(0.5)


def test_update_increases_winner_rating():
    model = EloModel(k=20, home_advantage=0.0, mov_multiplier=False)
    before_home = model.get_rating("Home")
    before_away = model.get_rating("Away")
    model.update("Home", "Away", 30, 10)
    assert model.get_rating("Home") > before_home
    assert model.get_rating("Away") < before_away


def test_ratings_are_zero_sum_without_mov():
    model = EloModel(k=20, home_advantage=0.0, mov_multiplier=False)
    model.update("Home", "Away", 20, 17)
    total = model.get_rating("Home") + model.get_rating("Away")
    assert total == pytest.approx(2 * DEFAULT_RATING)


def test_upset_win_produces_larger_swing_than_expected_win():
    model_a = EloModel(k=20, home_advantage=0.0)
    model_a.ratings = {"Big Favorite": 1700, "Underdog": 1300}
    before = model_a.get_rating("Underdog")
    model_a.update("Big Favorite", "Underdog", 10, 20, neutral_site=True)  # underdog wins on the road
    swing = model_a.get_rating("Underdog") - before
    assert swing > 20  # bigger than a plain K=20 update, thanks to MOV multiplier on a big upset


def test_process_games_chronological_skips_unplayed():
    model = EloModel()
    games = [
        {"home_team": "A", "away_team": "B", "home_score": None, "away_score": None},
        {"home_team": "A", "away_team": "B", "home_score": 24, "away_score": 20},
    ]
    model.process_games_chronological(games)
    assert model.get_rating("A") != DEFAULT_RATING

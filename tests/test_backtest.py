import numpy as np
import pandas as pd
import pytest

from models.backtest import run_walk_forward_gbm_classifier, run_walk_forward_gbm_regressor


def _synthetic_df(n=400, seed=0):
    rng = np.random.default_rng(seed)
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)
    margin = 5 * x1 - 2 * x2 + rng.normal(0, 3, n)
    home_win = (margin > 0).astype(int)
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "game_id": [f"g{i}" for i in range(n)],
            "game_date": dates.astype(str),
            "x1": x1,
            "x2": x2,
            "margin": margin,
            "home_win": home_win,
        }
    )


def test_walk_forward_classifier_never_trains_on_future_rows():
    df = _synthetic_df(n=300)
    result = run_walk_forward_gbm_classifier(df, ["x1", "x2"], "home_win", min_train_games=150, retrain_every=50)
    assert result.n_folds >= 1
    assert not result.predictions.empty
    # every predicted game_id's positional index must be >= min_train_games
    idx_lookup = {gid: i for i, gid in enumerate(df["game_id"])}
    min_test_idx = min(idx_lookup[gid] for gid in result.predictions["game_id"])
    assert min_test_idx >= 150


def test_walk_forward_classifier_no_duplicate_predictions():
    df = _synthetic_df(n=300)
    result = run_walk_forward_gbm_classifier(df, ["x1", "x2"], "home_win", min_train_games=150, retrain_every=50)
    assert result.predictions["game_id"].is_unique


def test_walk_forward_classifier_raises_on_insufficient_data():
    df = _synthetic_df(n=50)
    with pytest.raises(ValueError):
        run_walk_forward_gbm_classifier(df, ["x1", "x2"], "home_win", min_train_games=150, retrain_every=50)


def test_walk_forward_regressor_produces_residual_std():
    df = _synthetic_df(n=300)
    result = run_walk_forward_gbm_regressor(df, ["x1", "x2"], "margin", min_train_games=150, retrain_every=50)
    assert result.regression_metrics is not None
    assert result.regression_metrics["residual_std"] > 0
    assert result.regression_metrics["n"] == len(result.predictions)


def test_walk_forward_classifier_beats_random_on_learnable_signal():
    # sanity check: on a strongly learnable synthetic signal, out-of-sample
    # Brier should beat the coin-flip baseline of 0.25
    df = _synthetic_df(n=500, seed=1)
    result = run_walk_forward_gbm_classifier(df, ["x1", "x2"], "home_win", min_train_games=200, retrain_every=50)
    assert result.calibration is not None
    assert result.calibration.brier_score < 0.25

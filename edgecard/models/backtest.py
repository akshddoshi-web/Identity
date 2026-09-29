"""Walk-forward backtesting.

No random train/test splits, ever — a random split lets the model train on
games chronologically *after* some of its test games, which leaks future
information (season-long team strength, roster changes, etc.) into training
and inflates every metric. Instead:

  1. Sort all games chronologically.
  2. Start with an initial training window of `min_train_games`.
  3. Retrain (or expand-window retrain) every `retrain_every` games.
  4. Predict strictly on the next block of unseen future games.
  5. Slide forward; repeat until data is exhausted.

This mirrors how the model would actually have been deployed in production:
at no point does it see a game before predicting it.

Elo ratings are updated incrementally game-by-game in chronological order
(see models/elo.py), which is naturally walk-forward and leak-free by
construction — `run_walk_forward_elo` reflects that. The GBM walk-forward
loop is separate and explicit about retrain cadence since retraining an
XGBoost model every single game is expensive; retraining every N games is a
standard, defensible compromise as long as N is disclosed (it is, in the
returned `WalkForwardResult.retrain_every`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from models.elo import EloModel
from models.gbm_model import (
    RegressionModel,
    WinProbabilityModel,
    evaluate_classifier,
    fit_win_probability_model,
    CalibrationReport,
)


@dataclass
class WalkForwardResult:
    predictions: pd.DataFrame          # game_id, game_date, y_true, y_pred_prob / y_pred_margin
    retrain_every: int
    min_train_games: int
    n_folds: int
    calibration: CalibrationReport | None = None
    regression_metrics: dict | None = None


def run_walk_forward_elo(games_sorted: pd.DataFrame, elo_model: EloModel | None = None) -> pd.DataFrame:
    """games_sorted: chronologically sorted DataFrame with home_team, away_team,
    home_score, away_score, neutral_site, game_id, game_date.

    Returns a frame with each game's PRE-GAME Elo-implied win probability
    (computed before that game updates the ratings) — this is what "walk
    forward" means for Elo: ratings only ever reflect games strictly earlier
    in time than the one being predicted.

    Pass a sport-configured `elo_model` (see models.elo.build_elo_for_sport)
    to use that sport's K-factor and home-advantage instead of EloModel()'s
    generic defaults. The instance is mutated in place as games are
    processed, so after this call `elo_model.ratings` holds each team's
    CURRENT rating (as of the last game in `games_sorted`) — useful for
    projecting ratings onto a team's next, not-yet-played game (see
    models/production.py).
    """
    model = elo_model if elo_model is not None else EloModel()
    rows = []
    for _, g in games_sorted.iterrows():
        prob_home = model.win_probability(g["home_team"], g["away_team"], g.get("neutral_site", False))
        rows.append(
            {
                "game_id": g["game_id"],
                "game_date": g["game_date"],
                "elo_prob_home": prob_home,
                "home_elo_pre": model.get_rating(g["home_team"]),
                "away_elo_pre": model.get_rating(g["away_team"]),
            }
        )
        if pd.notna(g.get("home_score")) and pd.notna(g.get("away_score")):
            model.update(g["home_team"], g["away_team"], g["home_score"], g["away_score"], g.get("neutral_site", False))
    return pd.DataFrame(rows)


def run_walk_forward_gbm_classifier(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    min_train_games: int,
    retrain_every: int,
    calibration_holdout_frac: float = 0.15,
) -> WalkForwardResult:
    """df must already be sorted ascending by game_date and contain
    feature_cols + target_col with no missing target rows.
    """
    df = df.reset_index(drop=True)
    n = len(df)
    if n <= min_train_games:
        raise ValueError(
            f"Only {n} games available but min_train_games={min_train_games}. "
            "Need more history before a walk-forward backtest is meaningful."
        )

    preds = []
    fold_starts = list(range(min_train_games, n, retrain_every))
    n_folds = len(fold_starts)

    for fold_idx, start in enumerate(fold_starts):
        train_df = df.iloc[:start]
        test_end = min(start + retrain_every, n)
        test_df = df.iloc[start:test_end]
        if test_df.empty or train_df.empty:
            continue

        # chronological (not random) calibration holdout — see
        # fit_win_probability_model's docstring for why.
        model = fit_win_probability_model(train_df, feature_cols, target_col, calibration_holdout_frac)
        y_prob = model.predict_proba(test_df[feature_cols])
        fold_preds = pd.DataFrame(
            {
                "game_id": test_df["game_id"].values,
                "game_date": test_df["game_date"].values,
                "y_true": test_df[target_col].values,
                "y_pred_prob": y_prob,
                "fold": fold_idx,
            }
        )
        preds.append(fold_preds)

    all_preds = pd.concat(preds, ignore_index=True) if preds else pd.DataFrame(
        columns=["game_id", "game_date", "y_true", "y_pred_prob", "fold"]
    )
    calib = evaluate_classifier(all_preds["y_true"], all_preds["y_pred_prob"]) if len(all_preds) else None

    return WalkForwardResult(
        predictions=all_preds,
        retrain_every=retrain_every,
        min_train_games=min_train_games,
        n_folds=n_folds,
        calibration=calib,
    )


def run_walk_forward_gbm_regressor(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    min_train_games: int,
    retrain_every: int,
) -> WalkForwardResult:
    df = df.reset_index(drop=True)
    n = len(df)
    if n <= min_train_games:
        raise ValueError(f"Only {n} games available but min_train_games={min_train_games}.")

    preds = []
    fold_starts = list(range(min_train_games, n, retrain_every))
    for fold_idx, start in enumerate(fold_starts):
        train_df = df.iloc[:start]
        test_end = min(start + retrain_every, n)
        test_df = df.iloc[start:test_end]
        if test_df.empty or train_df.empty:
            continue

        model = RegressionModel()
        model.fit(train_df[feature_cols], train_df[target_col])
        y_pred = model.predict(test_df[feature_cols])
        fold_preds = pd.DataFrame(
            {
                "game_id": test_df["game_id"].values,
                "game_date": test_df["game_date"].values,
                "y_true": test_df[target_col].values,
                "y_pred": y_pred,
                "fold": fold_idx,
            }
        )
        preds.append(fold_preds)

    all_preds = pd.concat(preds, ignore_index=True) if preds else pd.DataFrame(
        columns=["game_id", "game_date", "y_true", "y_pred", "fold"]
    )
    metrics = None
    if len(all_preds):
        resid = all_preds["y_true"] - all_preds["y_pred"]
        metrics = {
            "mae": float(resid.abs().mean()),
            "rmse": float(np.sqrt((resid ** 2).mean())),
            "residual_std": float(resid.std()),  # feed this into margin_to_win_prob's sigma
            "n": int(len(all_preds)),
        }

    return WalkForwardResult(
        predictions=all_preds,
        retrain_every=retrain_every,
        min_train_games=min_train_games,
        n_folds=len(fold_starts),
        regression_metrics=metrics,
    )

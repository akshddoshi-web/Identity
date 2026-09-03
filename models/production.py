"""Final production model fitting: one win-probability classifier and two
regressors (margin, total) per sport, fit on ALL available historical data,
for use predicting a slate of not-yet-played games.

This is deliberately separate from models/backtest.py's walk-forward loop.
Walk-forward exists to answer "how would this approach have performed out of
sample" — it retrains repeatedly and throws most fits away. A live system
instead wants exactly one current model that has seen everything up to now.
The two are connected here in one place: `train_production_models` still
RUNS a walk-forward backtest first, not to keep its fold models, but to get
two things a live model cannot honestly report about itself: out-of-sample
calibration (Brier/log loss) and out-of-sample residual standard deviation
for the margin/total regressors (`sigma_margin`/`sigma_total`), which is
what turns a point prediction into a probability via
models.gbm_model.margin_to_win_prob. Using the FINAL model's own in-sample
residuals for sigma would understate real uncertainty — a model always fits
its own training residuals better than it will do on new games.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from models.backtest import run_walk_forward_elo, run_walk_forward_gbm_classifier, run_walk_forward_gbm_regressor
from models.elo import EloModel, build_elo_for_sport
from models.features import build_feature_frame, feature_columns, select_populated_feature_columns
from models.gbm_model import RegressionModel, fit_win_probability_model, WinProbabilityModel


class InsufficientHistoryError(Exception):
    """Raised when there isn't enough historical data to responsibly fit and
    validate a production model for a sport. The caller (scripts/daily_report.py)
    is expected to skip that sport and say so explicitly — never fall back to
    an unvalidated model just to produce a pick."""


@dataclass
class ProductionModels:
    sport: str
    win_model: WinProbabilityModel
    margin_model: RegressionModel
    total_model: RegressionModel
    feat_cols: list[str]
    elo_ratings: dict[str, float]     # each team's CURRENT rating, post-history
    sigma_margin: float                # for margin_to_win_prob (spread cover probability)
    sigma_total: float                  # for margin_to_win_prob (over/under probability)
    n_train_games: int
    min_train_games: int
    oos_brier: float | None            # walk-forward out-of-sample Brier score, if available
    oos_logloss: float | None
    oos_n: int                          # number of walk-forward OOS predictions behind the above


def _default_retrain_every(min_train_games: int) -> int:
    return max(50, min_train_games // 10)


def train_production_models(
    games_hist: pd.DataFrame,
    stats_hist: pd.DataFrame,
    sport: str,
    cfg: dict,
    min_train_games: int | None = None,
    retrain_every: int | None = None,
) -> ProductionModels:
    sport_cfg = cfg["sports"][sport]
    min_train_games = min_train_games if min_train_games is not None else sport_cfg["rolling_window_games"]
    retrain_every = retrain_every if retrain_every is not None else _default_retrain_every(min_train_games)

    games_sorted = games_hist.sort_values("game_date").reset_index(drop=True)

    elo_model = build_elo_for_sport(sport, cfg)
    elo_df = run_walk_forward_elo(games_sorted, elo_model=elo_model).merge(
        games_sorted[["game_id", "home_team", "away_team"]], on="game_id"
    )
    elo_by_game = {
        row["game_id"]: {row["home_team"]: row["home_elo_pre"], row["away_team"]: row["away_elo_pre"]}
        for _, row in elo_df.iterrows()
    }
    current_elo_ratings = elo_model.snapshot()  # mutated in place by run_walk_forward_elo above

    feat_df = build_feature_frame(games_sorted, stats_hist, sport, elo_ratings_by_date=elo_by_game)
    all_feat_cols = feature_columns(feat_df)
    feat_cols = select_populated_feature_columns(feat_df, all_feat_cols)

    model_df = feat_df.dropna(subset=feat_cols + ["home_win", "margin", "total"]).reset_index(drop=True)
    model_df = model_df.sort_values("game_date").reset_index(drop=True)

    if len(model_df) <= min_train_games + retrain_every:
        raise InsufficientHistoryError(
            f"{sport}: only {len(model_df)} usable historical games after feature warmup, "
            f"but a walk-forward validation needs at least min_train_games + retrain_every "
            f"= {min_train_games} + {retrain_every} = {min_train_games + retrain_every}. "
            "Refusing to fit an unvalidated production model — get more history or lower "
            "sports.<SPORT>.rolling_window_games in config/config.yaml if you understand the "
            "tradeoff (less validation data behind the calibration/sigma estimates)."
        )

    wf_clf = run_walk_forward_gbm_classifier(model_df, feat_cols, "home_win", min_train_games, retrain_every)
    wf_margin = run_walk_forward_gbm_regressor(model_df, feat_cols, "margin", min_train_games, retrain_every)
    wf_total = run_walk_forward_gbm_regressor(model_df, feat_cols, "total", min_train_games, retrain_every)

    oos_brier = wf_clf.calibration.brier_score if wf_clf.calibration else None
    oos_logloss = wf_clf.calibration.log_loss if wf_clf.calibration else None
    oos_n = wf_clf.calibration.n_samples if wf_clf.calibration else 0

    sigma_margin = (
        wf_margin.regression_metrics["residual_std"] if wf_margin.regression_metrics else float(model_df["margin"].std())
    )
    sigma_total = (
        wf_total.regression_metrics["residual_std"] if wf_total.regression_metrics else float(model_df["total"].std())
    )

    # Final production fit: ALL available history, one model each. Uses the
    # same chronological-holdout calibration as every walk-forward fold
    # (fit_win_probability_model), just fit once instead of per-fold.
    win_model = fit_win_probability_model(model_df, feat_cols, "home_win")
    margin_model = RegressionModel().fit(model_df[feat_cols], model_df["margin"])
    total_model = RegressionModel().fit(model_df[feat_cols], model_df["total"])

    return ProductionModels(
        sport=sport,
        win_model=win_model,
        margin_model=margin_model,
        total_model=total_model,
        feat_cols=feat_cols,
        elo_ratings=current_elo_ratings,
        sigma_margin=sigma_margin,
        sigma_total=sigma_total,
        n_train_games=len(model_df),
        min_train_games=min_train_games,
        oos_brier=oos_brier,
        oos_logloss=oos_logloss,
        oos_n=oos_n,
    )

"""Gradient-boosted models: win probability (classification), margin
(regression), and total (regression), plus calibration reporting.

Accuracy is not the metric that matters for a betting model — a model that's
"right" 55% of the time but badly miscalibrated (e.g. always says 70% when
the true rate is 55%) will look great on accuracy and lose money against a
market that's actually closer to right. So every classifier here reports
Brier score and log loss, and `calibration_table` buckets predictions to show
whether "the model says 65%" actually happens ~65% of the time.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error, mean_squared_error
from sklearn.isotonic import IsotonicRegression


@dataclass
class CalibrationReport:
    brier_score: float
    log_loss: float
    n_samples: int
    calibration_table: pd.DataFrame  # bucket, mean_predicted, mean_actual, n

    def summary(self) -> str:
        lines = [
            f"n={self.n_samples}  Brier={self.brier_score:.4f}  LogLoss={self.log_loss:.4f}",
            "  (lower is better for both; a coin-flip model scores Brier=0.25, LogLoss=0.693)",
        ]
        if self.n_samples < 200:
            lines.append(
                "  WARNING: n<200 — calibration numbers here are NOT statistically reliable. "
                "Treat as a smoke-test, not evidence of skill."
            )
        return "\n".join(lines)


def calibration_table(y_true: np.ndarray, y_prob: np.ndarray, n_buckets: int = 10) -> pd.DataFrame:
    df = pd.DataFrame({"y_true": y_true, "y_prob": y_prob})
    df["bucket"] = pd.qcut(df["y_prob"], q=min(n_buckets, df["y_prob"].nunique()), duplicates="drop")
    grouped = df.groupby("bucket", observed=True).agg(
        mean_predicted=("y_prob", "mean"), mean_actual=("y_true", "mean"), n=("y_true", "size")
    )
    return grouped.reset_index()


def evaluate_classifier(y_true: np.ndarray, y_prob: np.ndarray) -> CalibrationReport:
    # np.asarray() on a pandas nullable Int64 Series (which home_win is,
    # from build_feature_frame) yields an OBJECT-dtype array, not int64 —
    # sklearn's type_of_target then can't tell it's binary and raises. Force
    # a concrete numeric dtype so this works regardless of the pandas dtype
    # the caller happened to hand in.
    y_true = np.asarray(y_true, dtype=np.float64)
    y_prob = np.clip(np.asarray(y_prob, dtype=np.float64), 1e-6, 1 - 1e-6)
    return CalibrationReport(
        brier_score=float(brier_score_loss(y_true, y_prob)),
        log_loss=float(log_loss(y_true, y_prob)),
        n_samples=len(y_true),
        calibration_table=calibration_table(y_true, y_prob),
    )


class WinProbabilityModel:
    """XGBoost classifier for home-win probability, with optional isotonic
    calibration fit on a held-out slice (never on the same data used to fit
    the base model or to evaluate it — see models/backtest.py for the
    walk-forward split that keeps this honest)."""

    def __init__(self, params: dict | None = None):
        self.params = params or dict(
            n_estimators=300,
            max_depth=3,
            learning_rate=0.03,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            objective="binary:logistic",
            eval_metric="logloss",
            n_jobs=-1,
        )
        self.model = xgb.XGBClassifier(**self.params)
        self.calibrator: IsotonicRegression | None = None
        self.feature_names_: list[str] | None = None

    def fit(self, X: pd.DataFrame, y: pd.Series, X_cal: pd.DataFrame | None = None, y_cal: pd.Series | None = None):
        self.feature_names_ = list(X.columns)
        self.model.fit(X, y)
        if X_cal is not None and y_cal is not None and len(X_cal) >= 50:
            raw = self.model.predict_proba(X_cal)[:, 1]
            self.calibrator = IsotonicRegression(out_of_bounds="clip")
            self.calibrator.fit(raw, y_cal)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        raw = self.model.predict_proba(X[self.feature_names_])[:, 1]
        if self.calibrator is not None:
            return self.calibrator.predict(raw)
        return raw


def fit_win_probability_model(
    train_df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    calibration_holdout_frac: float = 0.15,
    params: dict | None = None,
) -> WinProbabilityModel:
    """Fits a WinProbabilityModel with an isotonic calibration holdout carved
    from the CHRONOLOGICAL TAIL of `train_df` (the most recent games before
    whatever comes next), never a random sample — calibrating on a random
    slice would let some "future" games leak into calibration for a model
    that's about to predict on games older than them. `train_df` must
    already be sorted ascending by date.

    Shared by models/backtest.py's walk-forward loop (one call per fold) and
    models/production.py's final production fit (one call on the full
    history) so both paths compute calibration identically.
    """
    cal_n = max(50, int(len(train_df) * calibration_holdout_frac))
    cal_n = min(cal_n, len(train_df) - 50) if len(train_df) > 100 else 0

    if cal_n > 0:
        fit_df, cal_df = train_df.iloc[:-cal_n], train_df.iloc[-cal_n:]
    else:
        fit_df, cal_df = train_df, None

    model = WinProbabilityModel(params)
    model.fit(
        fit_df[feature_cols],
        fit_df[target_col],
        X_cal=cal_df[feature_cols] if cal_df is not None else None,
        y_cal=cal_df[target_col] if cal_df is not None else None,
    )
    return model


class RegressionModel:
    """XGBoost regressor, used for both margin and total prediction."""

    def __init__(self, params: dict | None = None):
        self.params = params or dict(
            n_estimators=300,
            max_depth=3,
            learning_rate=0.03,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            objective="reg:squarederror",
            n_jobs=-1,
        )
        self.model = xgb.XGBRegressor(**self.params)
        self.feature_names_: list[str] | None = None

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.feature_names_ = list(X.columns)
        self.model.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict(X[self.feature_names_])

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> dict:
        pred = self.predict(X)
        return {
            "mae": float(mean_absolute_error(y, pred)),
            "rmse": float(np.sqrt(mean_squared_error(y, pred))),
            "n": int(len(y)),
        }


def margin_to_win_prob(predicted_margin: np.ndarray, sigma: float) -> np.ndarray:
    """Converts a predicted point margin to a win probability assuming
    margins are approximately normal with std `sigma` (fit empirically per
    sport from backtest residuals — do NOT hardcode a league-wide constant
    without checking it against your own residual distribution)."""
    from scipy.stats import norm

    return norm.cdf(predicted_margin / sigma)

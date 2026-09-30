"""Game-level model: mean (gradient boosting) + fitted variance + key-number
distribution, and a market-aware calibration layer.

Two kinds of probability come out of this module:

  model_only   calibrated (isotonic) probability from our distribution alone.
               Reported for calibration plots / Brier scores.
  final        market-anchored: logit(p) = logit(no-vig market) + w * (logit(model)
               - logit(market)), with w in [0, 1] fitted ONLY on earlier seasons'
               out-of-sample predictions and set to 0 unless a likelihood-ratio
               test says the model's disagreement with the market is real. If
               our model carries no information the market hasn't priced, the
               final probability IS the market — no edges, no bets.
               That is deliberate: an edge has to be earned out of sample
               before the card will act on it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.isotonic import IsotonicRegression

from models.distributions import (
    MARGIN_SUPPORT, TOTAL_SUPPORT, DiscreteDist, JointSpec, KeyWeights, SigmaModel,
    moneyline_prob, spread_prob, total_prob,
)

XGB_PARAMS = dict(n_estimators=250, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8,
                  reg_lambda=2.0, min_child_weight=5, objective="reg:squarederror", n_jobs=4, verbosity=0)


def _logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


@dataclass
class GameModel:
    feature_cols: list[str]
    margin_model: xgb.XGBRegressor | None = None
    total_model: xgb.XGBRegressor | None = None
    sigma_margin: SigmaModel | None = None
    sigma_total: SigmaModel | None = None
    kw_margin: KeyWeights | None = None
    kw_total: KeyWeights | None = None
    joint: JointSpec = field(default_factory=JointSpec)
    n_train: int = 0

    def fit(self, train: pd.DataFrame, oos_resid: pd.DataFrame | None = None) -> "GameModel":
        """`oos_resid` (optional): out-of-sample residuals from earlier folds,
        used for the variance model so sigma reflects real prediction error
        rather than in-sample fit. Falls back to a split of `train`."""
        tr = train.dropna(subset=["margin", "total_pts"])
        X = tr[self.feature_cols].astype(float)
        self.margin_model = xgb.XGBRegressor(**XGB_PARAMS).fit(X, tr["margin"])
        self.total_model = xgb.XGBRegressor(**XGB_PARAMS).fit(X, tr["total_pts"])
        self.n_train = len(tr)

        if oos_resid is None or len(oos_resid) < 200:
            # honest-ish fallback: fit on the older 75%, residuals on the newest 25%
            cut = int(len(tr) * 0.75)
            a, b = tr.iloc[:cut], tr.iloc[cut:]
            mm = xgb.XGBRegressor(**XGB_PARAMS).fit(a[self.feature_cols].astype(float), a["margin"])
            tm = xgb.XGBRegressor(**XGB_PARAMS).fit(a[self.feature_cols].astype(float), a["total_pts"])
            pm = mm.predict(b[self.feature_cols].astype(float))
            pt = tm.predict(b[self.feature_cols].astype(float))
            oos_resid = pd.DataFrame({"resid_margin": b["margin"].values - pm, "resid_total": b["total_pts"].values - pt,
                                      "pred_margin": pm, "pred_total": pt,
                                      "margin": b["margin"].values, "total_pts": b["total_pts"].values})
        self.sigma_margin = SigmaModel.fit(oos_resid["resid_margin"], oos_resid["pred_total"])
        self.sigma_total = SigmaModel.fit(oos_resid["resid_total"], oos_resid["pred_total"])
        self.kw_margin = KeyWeights.fit(oos_resid["margin"], MARGIN_SUPPORT, center=oos_resid["pred_margin"],
                                        sigma=float(oos_resid["resid_margin"].std()))
        self.kw_total = KeyWeights.fit(oos_resid["total_pts"], TOTAL_SUPPORT, center=oos_resid["pred_total"],
                                       sigma=float(oos_resid["resid_total"].std()), clip=(0.5, 1.8))
        self.joint = JointSpec.fit(oos_resid["resid_margin"], oos_resid["resid_total"], oos_resid["pred_margin"])
        return self

    def predict_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df[self.feature_cols].astype(float)
        pm = self.margin_model.predict(X)
        pt = self.total_model.predict(X)
        return pd.DataFrame({"game_id": df["game_id"].values, "pred_margin": pm, "pred_total": pt,
                             "sigma_margin": self.sigma_margin(pt), "sigma_total": self.sigma_total(pt)})

    def dists(self, pred_margin: float, pred_total: float) -> tuple[DiscreteDist, DiscreteDist]:
        sm = float(self.sigma_margin(pred_total))
        st = float(self.sigma_total(pred_total))
        return (DiscreteDist.build(pred_margin, sm, self.kw_margin),
                DiscreteDist.build(pred_total, st, self.kw_total))


# --------------------------------------------------------------------------- #
# market helpers
# --------------------------------------------------------------------------- #

def american_to_prob(price) -> float:
    price = float(price)
    return 100 / (price + 100) if price > 0 else -price / (-price + 100)


def novig_pair(p_a_price, p_b_price) -> tuple[float, float]:
    a, b = american_to_prob(p_a_price), american_to_prob(p_b_price)
    s = a + b
    return a / s, b / s


def market_probs_row(r: pd.Series) -> dict[str, float]:
    """No-vig closing probabilities for home ML, home spread cover, over."""
    out = {}
    if pd.notna(r.get("home_moneyline")) and pd.notna(r.get("away_moneyline")):
        out["ml_home"] = novig_pair(r["home_moneyline"], r["away_moneyline"])[0]
    if pd.notna(r.get("home_spread_odds")) and pd.notna(r.get("away_spread_odds")):
        out["spread_home"] = novig_pair(r["home_spread_odds"], r["away_spread_odds"])[0]
    if pd.notna(r.get("over_odds")) and pd.notna(r.get("under_odds")):
        out["over"] = novig_pair(r["over_odds"], r["under_odds"])[0]
    return out


def model_market_probs(gm: GameModel, preds: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """For each game: model probability (conditional on no push) of home ML,
    home cover at the closing spread, and over at the closing total, plus
    the no-vig market probability of the same events."""
    f = frame.set_index("game_id")
    rows = []
    for _, p in preds.iterrows():
        r = f.loc[p["game_id"]]
        md, td = gm.dists(p["pred_margin"], p["pred_total"])
        mk = market_probs_row(r)
        row = {"game_id": p["game_id"], "pred_margin": p["pred_margin"], "pred_total": p["pred_total"]}
        row["model_ml_home"] = moneyline_prob(md, "home").cover_given_no_push
        row["mkt_ml_home"] = mk.get("ml_home", np.nan)
        if pd.notna(r.get("spread_line")):
            home_point = -float(r["spread_line"])  # nflverse: spread_line = expected home margin
            row["home_point"] = home_point
            row["model_spread_home"] = spread_prob(md, home_point, "home").cover_given_no_push
        row["mkt_spread_home"] = mk.get("spread_home", np.nan)
        if pd.notna(r.get("total_line")):
            row["total_line"] = float(r["total_line"])
            row["model_over"] = total_prob(td, float(r["total_line"]), "over").cover_given_no_push
        row["mkt_over"] = mk.get("over", np.nan)
        # outcomes
        if pd.notna(r.get("margin")):
            m, t = float(r["margin"]), float(r["total_pts"])
            row["y_ml_home"] = 1.0 if m > 0 else 0.0 if m < 0 else np.nan
            if "home_point" in row:
                v = m + row["home_point"]
                row["y_spread_home"] = 1.0 if v > 0 else 0.0 if v < 0 else np.nan
            if "total_line" in row:
                v = t - row["total_line"]
                row["y_over"] = 1.0 if v > 0 else 0.0 if v < 0 else np.nan
            row["margin"], row["total_pts"] = m, t
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# calibration layers
# --------------------------------------------------------------------------- #

MARKETS = ("ml_home", "spread_home", "over")


def fit_model_weight(p_model: np.ndarray, p_mkt: np.ndarray, y: np.ndarray, alpha_chi2: float = 5.412) -> dict:
    """Fits w in [0, 1] for  p = sigmoid(logit(mkt) + w * (logit(model) - logit(mkt))).

    The market is the anchor (intercept 0, market weight 1): the only thing
    learned is how much of our model's DISAGREEMENT with the market is real.
    w is kept only if a likelihood-ratio test against w = 0 is significant
    (chi2(1) > 5.412, i.e. one-sided alpha 0.01 — strict on purpose: a false
    edge costs money, and three markets are tested); otherwise w = 0 and the
    final probability equals the market — no edge, no bet.
    """
    lm, d = _logit(p_mkt), _logit(p_model) - _logit(p_mkt)
    y = np.asarray(y, dtype=float)
    grid = np.linspace(0, 1, 101)

    def nll(w):
        p = 1 / (1 + np.exp(-(lm + w * d)))
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return -np.sum(y * np.log(p) + (1 - y) * np.log(1 - p))

    vals = np.array([nll(w) for w in grid])
    w_hat = float(grid[vals.argmin()])
    lr = 2 * (nll(0.0) - vals.min())
    return {"w_hat": w_hat, "lr_stat": float(lr), "significant": bool(lr > alpha_chi2),
            "w": w_hat if lr > alpha_chi2 else 0.0, "n": int(len(y))}


@dataclass
class Calibrators:
    """Fitted on earlier out-of-sample predictions only."""

    iso: dict[str, IsotonicRegression] = field(default_factory=dict)
    weights: dict[str, dict] = field(default_factory=dict)
    n: dict[str, int] = field(default_factory=dict)

    @property
    def stack_coef(self) -> dict[str, dict]:
        return self.weights

    @classmethod
    def fit(cls, oos: pd.DataFrame, min_n: int = 250) -> "Calibrators":
        c = cls()
        for m in MARKETS:
            if f"model_{m}" not in oos or f"y_{m}" not in oos:
                continue
            d = oos.dropna(subset=[f"model_{m}", f"y_{m}"])
            if len(d) >= min_n:
                iso = IsotonicRegression(out_of_bounds="clip", y_min=0.01, y_max=0.99)
                iso.fit(d[f"model_{m}"], d[f"y_{m}"])
                c.iso[m] = iso
            d2 = d.dropna(subset=[f"mkt_{m}"])
            if len(d2) >= min_n:
                c.weights[m] = fit_model_weight(d2[f"model_{m}"].values, d2[f"mkt_{m}"].values, d2[f"y_{m}"].values)
            c.n[m] = len(d)
        return c

    def w(self, m: str) -> float:
        return float(self.weights.get(m, {}).get("w", 0.0))

    def model_only(self, m: str, p: np.ndarray) -> np.ndarray:
        return self.iso[m].predict(p) if m in self.iso else np.asarray(p)

    def final(self, m: str, p_model: np.ndarray, p_mkt: np.ndarray) -> np.ndarray:
        """Market-anchored probability; equals the market when w = 0."""
        p_model, p_mkt = np.asarray(p_model, dtype=float), np.asarray(p_mkt, dtype=float)
        w = self.w(m)
        z = _logit(p_mkt) + w * (_logit(p_model) - _logit(p_mkt))
        out = 1 / (1 + np.exp(-z))
        return np.where(np.isnan(p_mkt), np.nan, out)

    def shift(self, m: str, p_model: float, p_mkt_this_side: float) -> float:
        """Same anchoring for lines other than the closing line (alternate
        lines, props, parlay legs)."""
        return float(self.final(m, np.array([p_model]), np.array([p_mkt_this_side]))[0])

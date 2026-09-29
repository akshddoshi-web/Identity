"""Outcome distributions for game margin and total.

A single point prediction can't price a spread, a total, an alternate line
or a parlay. Here each game gets a full discrete distribution over integer
margins and totals:

  p(k) ∝ Normal(k; mu, sigma) * w(k)

mu comes from the mean model (gradient boosting), sigma from a fitted
variance model, and w(k) is a key-number reweighting learned from history:
the ratio of how often each final margin actually happens to how often a
smooth normal says it should. That is what puts extra mass on 3 and 7 in
the NFL (and removes it from 0 — ties are rare), which matters a lot for
pricing -2.5 vs -3.5.

Probabilities for bets (push-aware):
  P(side wins), P(push), P(side loses) for any line, and the conditional
  cover probability used for log-loss comparisons.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import norm

MARGIN_SUPPORT = np.arange(-80, 81)
TOTAL_SUPPORT = np.arange(0, 181)


@dataclass
class KeyWeights:
    support: np.ndarray
    weights: np.ndarray

    @classmethod
    def fit(cls, values: np.ndarray, support: np.ndarray, center: np.ndarray | None = None,
            sigma: float | None = None, pseudo: float = 3.0, clip: tuple[float, float] = (0.15, 3.0)) -> "KeyWeights":
        """Estimates w(k) from observed outcomes. If per-game centers are
        given, weights come from residual-aligned counts so the ratio isn't
        dominated by where the average game sits."""
        values = np.asarray(values, dtype=float)
        values = values[~np.isnan(values)]
        counts = np.array([(values == k).sum() for k in support], dtype=float)
        if center is None:
            mu, sd = values.mean(), values.std()
            smooth = norm.pdf(support, mu, sd) * len(values)
        else:
            center = np.asarray(center, dtype=float)
            sd = sigma or float(np.std(values - center))
            smooth = np.zeros_like(support, dtype=float)
            for c in center:
                smooth += norm.pdf(support, c, sd)
        w = (counts + pseudo) / (smooth + pseudo)
        return cls(support=support, weights=np.clip(w, *clip))

    @classmethod
    def flat(cls, support: np.ndarray) -> "KeyWeights":
        return cls(support=support, weights=np.ones_like(support, dtype=float))


@dataclass
class DiscreteDist:
    support: np.ndarray
    pmf: np.ndarray

    @classmethod
    def build(cls, mu: float, sigma: float, kw: KeyWeights) -> "DiscreteDist":
        base = norm.cdf(kw.support + 0.5, mu, sigma) - norm.cdf(kw.support - 0.5, mu, sigma)
        p = base * kw.weights
        s = p.sum()
        return cls(kw.support, p / s if s > 0 else base / base.sum())

    @property
    def mean(self) -> float:
        return float((self.support * self.pmf).sum())

    def prob_greater(self, x: float) -> float:
        return float(self.pmf[self.support > x].sum())

    def prob_equal(self, x: float) -> float:
        return float(self.pmf[self.support == x].sum()) if float(x).is_integer() else 0.0

    def sample(self, n: int, rng: np.random.Generator) -> np.ndarray:
        return rng.choice(self.support, size=n, p=self.pmf)


@dataclass
class BetProb:
    win: float
    push: float
    lose: float

    @property
    def cover_given_no_push(self) -> float:
        d = self.win + self.lose
        return self.win / d if d > 0 else 0.5


def spread_prob(margin: DiscreteDist, side_point: float, side: str) -> BetProb:
    """side='home': bet home at `side_point` (e.g. -3.5). Home covers when
    margin + point > 0. side='away': away covers when -margin + point > 0."""
    if side == "home":
        win = margin.prob_greater(-side_point)
        push = margin.prob_equal(-side_point)
    else:
        win = float(margin.pmf[margin.support < side_point].sum())
        push = margin.prob_equal(side_point)
    return BetProb(win, push, max(0.0, 1 - win - push))


def total_prob(total: DiscreteDist, line: float, side: str) -> BetProb:
    over = total.prob_greater(line)
    push = total.prob_equal(line)
    under = max(0.0, 1 - over - push)
    return BetProb(over, push, under) if side == "over" else BetProb(under, push, over)


def moneyline_prob(margin: DiscreteDist, side: str, tie_splits: bool = True) -> BetProb:
    """NFL ties are rare (and a tie refunds most moneylines, i.e. a push);
    NBA has no ties. Mass at 0 is treated as a push."""
    home = margin.prob_greater(0)
    tie = margin.prob_equal(0)
    away = max(0.0, 1 - home - tie)
    return BetProb(home, tie, away) if side == "home" else BetProb(away, tie, home)


# --------------------------------------------------------------------------- #
# Variance model
# --------------------------------------------------------------------------- #

@dataclass
class SigmaModel:
    """sigma = a + b * predicted_total (clipped). For margins b is fitted on
    the same way (larger expected totals -> larger margin variance)."""

    a: float
    b: float
    lo: float
    hi: float

    def __call__(self, pred_total: np.ndarray | float) -> np.ndarray:
        return np.clip(self.a + self.b * np.asarray(pred_total, dtype=float), self.lo, self.hi)

    @classmethod
    def fit(cls, resid: np.ndarray, pred_total: np.ndarray) -> "SigmaModel":
        resid = np.asarray(resid, dtype=float)
        pt = np.asarray(pred_total, dtype=float)
        ok = ~(np.isnan(resid) | np.isnan(pt))
        resid, pt = resid[ok], pt[ok]
        # E|r| = sigma * sqrt(2/pi) for a normal residual
        y = np.abs(resid) / np.sqrt(2 / np.pi)
        X = np.column_stack([np.ones_like(pt), pt])
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        sd = float(resid.std())
        return cls(a=float(coef[0]), b=float(coef[1]), lo=0.7 * sd, hi=1.3 * sd)


@dataclass
class JointSpec:
    """Correlation between margin and total residuals, oriented so that
    positive means 'the favourite beating its number goes with the over'."""

    rho_fav: float = 0.0

    @classmethod
    def fit(cls, resid_margin: np.ndarray, resid_total: np.ndarray, pred_margin: np.ndarray) -> "JointSpec":
        sgn = np.sign(pred_margin)
        sgn[sgn == 0] = 1
        a = np.asarray(resid_margin) * sgn
        b = np.asarray(resid_total)
        ok = ~(np.isnan(a) | np.isnan(b))
        if ok.sum() < 30:
            return cls(0.0)
        return cls(float(np.corrcoef(a[ok], b[ok])[0, 1]))

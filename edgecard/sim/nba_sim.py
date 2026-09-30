"""Game-level NBA simulation (margin + total, correlated), used for
same-game combinations of spread / moneyline / total. Player-level NBA
props are shadow-tracked only until the NBA props model is validated."""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from models.distributions import DiscreteDist
from sim.nfl_sim import GameSim


def simulate_nba_game(margin_dist: DiscreteDist, pred_total: float, sigma_total: float, rho_fav: float,
                      ev: pd.Series, n: int = 10000) -> GameSim:
    rng = np.random.default_rng(int(hashlib.md5(str(ev["game_key"]).encode()).hexdigest()[:6], 16))
    mu = margin_dist.mean
    sd = float(np.sqrt((margin_dist.pmf * (margin_dist.support - mu) ** 2).sum()))
    M = margin_dist.sample(n, rng).astype(float)
    M[M == 0] = rng.choice([-1.0, 1.0], size=(M == 0).sum())  # no ties in the NBA (OT)
    sgn = 1.0 if mu >= 0 else -1.0
    z = (M - mu) / max(sd, 1e-6)
    T = np.round(pred_total + sigma_total * (rho_fav * sgn * z + np.sqrt(max(1 - rho_fav ** 2, 0)) * rng.standard_normal(n)))
    T = np.where((T + M) % 2 == 1, T + 1, T)
    return GameSim(n=n, margin=M, total=T, home_pts=(T + M) / 2, away_pts=(T - M) / 2, stats={})

"""Monte Carlo simulation of bankroll paths.

The single most important guardrail in this repo: a backtest produces ONE
equity curve, and it is tempting to read that one curve as "what will
happen." It is one draw from a highly variable distribution. This module
simulates many independent draws of a betting sequence with a given
(win probability, price, stake-sizing rule) and shows the full spread of
outcomes — including how often even a genuinely profitable strategy
experiences a large drawdown or a long losing streak along the way.

Headline fact this module exists to put in front of the user: **even a
bettor with a true, durable 55% win probability at -110 (a real, rare, sharp-
level edge) will still have extended losing stretches and can hit
double-digit percentage drawdowns over a few hundred bets.** If your actual
results look "too smooth," be suspicious of your own accounting before you
celebrate.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from data_pipeline.config import load_config
from edge.devig import american_to_decimal


@dataclass
class MonteCarloResult:
    starting_bankroll: float
    n_simulations: int
    n_bets: int
    true_win_prob: float
    price: float
    stake_fraction: float           # fixed fraction of CURRENT bankroll staked each bet (fractional-Kelly-style)
    ending_bankrolls: np.ndarray     # shape (n_simulations,)
    max_drawdowns: np.ndarray         # shape (n_simulations,), one per sim
    paths_sample: np.ndarray            # shape (min(200, n_simulations), n_bets+1), for plotting

    def summary(self) -> dict:
        pct_ruined = float((self.ending_bankrolls <= self.starting_bankroll * 0.1).mean())
        pct_profitable = float((self.ending_bankrolls > self.starting_bankroll).mean())
        return {
            "median_ending_bankroll": float(np.median(self.ending_bankrolls)),
            "p10_ending_bankroll": float(np.percentile(self.ending_bankrolls, 10)),
            "p90_ending_bankroll": float(np.percentile(self.ending_bankrolls, 90)),
            "pct_simulations_profitable": pct_profitable,
            "pct_simulations_lost_90pct_or_more": pct_ruined,
            "median_max_drawdown_pct": float(np.median(self.max_drawdowns)),
            "p90_max_drawdown_pct": float(np.percentile(self.max_drawdowns, 90)),
        }

    def headline(self) -> str:
        s = self.summary()
        return (
            f"Monte Carlo ({self.n_simulations:,} sims x {self.n_bets} bets, "
            f"true win prob={self.true_win_prob:.1%}, price={self.price:+.0f}, "
            f"stake={self.stake_fraction:.1%} of bankroll/bet):\n"
            f"  Median ending bankroll: ${s['median_ending_bankroll']:,.0f} "
            f"(10th pct ${s['p10_ending_bankroll']:,.0f} / 90th pct ${s['p90_ending_bankroll']:,.0f})\n"
            f"  Profitable in {s['pct_simulations_profitable']:.1%} of simulations\n"
            f"  Lost 90%+ of bankroll in {s['pct_simulations_lost_90pct_or_more']:.1%} of simulations\n"
            f"  Median max drawdown: {s['median_max_drawdown_pct']:.1%} "
            f"(90th pct worst-case drawdown: {s['p90_max_drawdown_pct']:.1%})\n"
            "  Reminder: this is what variance looks like even when the edge is REAL. "
            "A single realized backtest curve is one draw from this same distribution."
        )


def simulate_bankroll_paths(
    true_win_prob: float,
    price: float,
    stake_fraction: float,
    starting_bankroll: float | None = None,
    n_simulations: int | None = None,
    n_bets: int | None = None,
    cfg: dict | None = None,
    seed: int | None = None,
) -> MonteCarloResult:
    """Simulates `n_simulations` independent sequences of `n_bets` bets, each
    staking a fixed `stake_fraction` of the CURRENT bankroll (fractional-
    Kelly-style compounding, matching how the Kelly sizer actually operates
    bet-to-bet — not fixed-dollar flat betting).
    """
    cfg = cfg or load_config()
    starting_bankroll = starting_bankroll if starting_bankroll is not None else cfg["bankroll"]["starting_bankroll"]
    n_simulations = n_simulations if n_simulations is not None else cfg["monte_carlo"]["n_simulations"]
    n_bets = n_bets if n_bets is not None else cfg["monte_carlo"]["n_bets_per_simulation"]

    rng = np.random.default_rng(seed)
    decimal_odds = american_to_decimal(price)
    net_odds = decimal_odds - 1.0  # profit multiple on a win, per unit staked

    outcomes = rng.random((n_simulations, n_bets)) < true_win_prob  # True = win

    bankrolls = np.full((n_simulations, n_bets + 1), starting_bankroll, dtype=float)
    for t in range(n_bets):
        stake = bankrolls[:, t] * stake_fraction
        stake = np.maximum(stake, 0.0)
        win_mask = outcomes[:, t]
        pnl = np.where(win_mask, stake * net_odds, -stake)
        bankrolls[:, t + 1] = np.maximum(bankrolls[:, t] + pnl, 0.0)  # bankroll floors at 0, can't go negative

    running_peak = np.maximum.accumulate(bankrolls, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        drawdowns = np.where(running_peak > 0, (bankrolls - running_peak) / running_peak, 0.0)
    max_drawdowns = drawdowns.min(axis=1)

    sample_n = min(200, n_simulations)
    sample_idx = rng.choice(n_simulations, size=sample_n, replace=False)

    return MonteCarloResult(
        starting_bankroll=starting_bankroll,
        n_simulations=n_simulations,
        n_bets=n_bets,
        true_win_prob=true_win_prob,
        price=price,
        stake_fraction=stake_fraction,
        ending_bankrolls=bankrolls[:, -1],
        max_drawdowns=max_drawdowns,
        paths_sample=bankrolls[sample_idx],
    )


def paths_to_dataframe(result: MonteCarloResult) -> pd.DataFrame:
    """Long-format frame (bet_index, sim_id, bankroll) for plotting a spaghetti
    chart of sample paths in the dashboard."""
    n_sims, n_steps = result.paths_sample.shape
    bet_idx = np.tile(np.arange(n_steps), n_sims)
    sim_id = np.repeat(np.arange(n_sims), n_steps)
    bankroll = result.paths_sample.flatten()
    return pd.DataFrame({"bet_index": bet_idx, "sim_id": sim_id, "bankroll": bankroll})

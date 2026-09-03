"""Bankroll tracking over time: equity curve, drawdown, and variance-adjusted
returns.

Raw ROI (total profit / total staked) is misleading in isolation because it
doesn't say anything about the ride it took to get there — a strategy that
returns +8% ROI with 40% max drawdown along the way is a very different
proposition from +8% ROI with 8% max drawdown, even though "the number" is
the same. This module reports both, plus a Sharpe-like ratio computed on
per-bet returns (not on your final ROI as a point estimate).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BankrollStats:
    starting_bankroll: float
    ending_bankroll: float
    n_bets: int
    total_staked: float
    total_profit: float
    roi_pct: float                 # total_profit / total_staked
    max_drawdown_pct: float          # peak-to-trough, on the equity curve
    sharpe_like_ratio: float          # mean(per-bet return) / std(per-bet return), NOT annualized
    win_rate: float


def compute_equity_curve(bet_ledger: pd.DataFrame, starting_bankroll: float) -> pd.DataFrame:
    """bet_ledger columns required: placed_at (sortable), stake, payout
    (net profit/loss, NULL/NaN until settled). Only settled bets (non-null
    payout) contribute to the curve; unsettled bets are ignored here (they
    still show as pending exposure elsewhere, not as realized bankroll
    change).
    """
    df = bet_ledger.dropna(subset=["payout"]).sort_values("placed_at").copy()
    df["bankroll"] = starting_bankroll + df["payout"].cumsum()
    df["running_peak"] = df["bankroll"].cummax()
    df["drawdown_pct"] = (df["bankroll"] - df["running_peak"]) / df["running_peak"]
    return df


def compute_bankroll_stats(bet_ledger: pd.DataFrame, starting_bankroll: float) -> BankrollStats:
    settled = bet_ledger.dropna(subset=["payout"])
    if settled.empty:
        return BankrollStats(starting_bankroll, starting_bankroll, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    curve = compute_equity_curve(bet_ledger, starting_bankroll)
    total_staked = float(settled["stake"].sum())
    total_profit = float(settled["payout"].sum())
    roi = total_profit / total_staked if total_staked > 0 else 0.0
    max_dd = float(curve["drawdown_pct"].min()) if not curve.empty else 0.0

    per_bet_return = settled["payout"] / settled["stake"].replace(0, np.nan)
    per_bet_return = per_bet_return.dropna()
    sharpe = (
        float(per_bet_return.mean() / per_bet_return.std(ddof=1))
        if len(per_bet_return) > 1 and per_bet_return.std(ddof=1) > 0
        else 0.0
    )
    win_rate = float((settled["result"] == "win").mean()) if "result" in settled.columns else float("nan")

    ending_bankroll = starting_bankroll + total_profit

    return BankrollStats(
        starting_bankroll=starting_bankroll,
        ending_bankroll=ending_bankroll,
        n_bets=len(settled),
        total_staked=total_staked,
        total_profit=total_profit,
        roi_pct=roi,
        max_drawdown_pct=max_dd,
        sharpe_like_ratio=sharpe,
        win_rate=win_rate,
    )


def bankroll_headline(stats: BankrollStats, min_sample_size: int = 200) -> str:
    lines = [
        f"Bankroll: ${stats.starting_bankroll:,.0f} -> ${stats.ending_bankroll:,.0f} "
        f"({stats.roi_pct:+.2%} ROI on ${stats.total_staked:,.0f} staked, n={stats.n_bets})",
        f"Max drawdown: {stats.max_drawdown_pct:.2%}   Sharpe-like ratio (per-bet): {stats.sharpe_like_ratio:.3f}",
    ]
    if stats.n_bets < min_sample_size:
        lines.append(
            f"WARNING: n={stats.n_bets} settled bets is below the {min_sample_size}-bet "
            "significance floor. ROI/drawdown/Sharpe above are descriptive only — "
            "do not treat them as evidence of a real edge yet."
        )
    return "\n".join(lines)

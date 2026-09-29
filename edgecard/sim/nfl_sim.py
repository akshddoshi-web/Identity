"""Correlated Monte Carlo simulation of an NFL game, down to player stats.

One simulation draw:
  1. margin M from the game's discrete (key-number) distribution;
     total T | M from a conditional normal with the fitted margin/total
     correlation (oriented to the favourite), then team points.
  2. team plays scale with the total's deviation from expectation (more
     points <-> more plays); each team's pass rate rises when it trails
     (game script), falls when it leads.
  3. shared efficiency shocks per team, tied to that team's points
     residual, scale every player's yards — so a big day for the QB is a
     big day for his receivers, and both go with the over.
  4. targets and carries are split among players by projected shares
     (multinomial), receptions ~ Binomial(targets, catch rate), yards ~
     Gamma per catch / Normal per carry; QB passing yards = the sum of his
     receivers' yards (completions and yards are exactly consistent).
  5. touchdowns ~ Poisson(0.105 x team points) split rushing/receiving and
     assigned to players by TD share.

Correlated multi-leg probabilities are computed by evaluating every leg on
the SAME draws and averaging the joint indicator — never by multiplying
independent leg probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from models.distributions import DiscreteDist
from models.nfl_props import TeamProjection

PASS_RATE_PER_POINT = 0.006   # pass-rate change per point of (opponent - own) score deviation
PLAYS_PER_TOTAL_POINT = 0.18  # extra plays per extra combined point
EFF_SD = 0.12
TD_PER_POINT = 0.105
TARGETS_PER_DROPBACK = 0.87  # ~6.5% sacks + ~4% throwaways/spikes/untargeted
SCRAMBLE_RATE = 0.045       # dropbacks that become QB scrambles
ATT_PER_DROPBACK = 0.93      # pass attempts recorded per dropback (sacks aren't attempts)


@dataclass
class GameSim:
    n: int
    margin: np.ndarray
    total: np.ndarray
    home_pts: np.ndarray
    away_pts: np.ndarray
    stats: dict[tuple[str, str], np.ndarray]  # (player, stat) -> array of length n

    def leg(self, spec: dict) -> np.ndarray:
        """Boolean array (win per draw) for one bet leg; pushes count as a
        non-win (conservative for parlays, where a push usually drops the
        leg — handled by the caller if needed)."""
        kind = spec["kind"]
        if kind == "spread":
            v = self.margin + spec["point"] if spec["side"] == "home" else -self.margin + spec["point"]
            return v > 0
        if kind == "moneyline":
            return self.margin > 0 if spec["side"] == "home" else self.margin < 0
        if kind == "total":
            return self.total > spec["point"] if spec["side"] == "over" else self.total < spec["point"]
        if kind == "prop":
            arr = self.stats.get((spec["player"], spec["market"]))
            if arr is None:
                return np.zeros(self.n, dtype=bool)
            if spec["market"] == "anytime_td":
                return arr >= 1 if spec["side"] == "over" else arr < 1
            return arr > spec["point"] if spec["side"] == "over" else arr < spec["point"]
        raise ValueError(kind)

    def prob(self, legs: list[dict]) -> float:
        ok = np.ones(self.n, dtype=bool)
        for L in legs:
            ok &= self.leg(L)
        return float(ok.mean())

    def push_prob(self, spec: dict) -> float:
        kind = spec["kind"]
        if kind == "spread":
            v = self.margin + spec["point"] if spec["side"] == "home" else -self.margin + spec["point"]
        elif kind == "total":
            v = self.total - spec["point"]
        elif kind == "prop" and spec["market"] != "anytime_td":
            arr = self.stats.get((spec["player"], spec["market"]))
            if arr is None:
                return 0.0
            v = arr - spec["point"]
        else:
            return 0.0
        return float((v == 0).mean())


def simulate_game(margin_dist: DiscreteDist, pred_total: float, sigma_total: float, rho_fav: float,
                  home: TeamProjection, away: TeamProjection, n: int = 10000, seed: int | None = None) -> GameSim:
    rng = np.random.default_rng(seed)
    mu_m = margin_dist.mean
    sd_m = float(np.sqrt((margin_dist.pmf * (margin_dist.support - mu_m) ** 2).sum()))
    M = margin_dist.sample(n, rng).astype(float)
    fav_sign = 1.0 if mu_m >= 0 else -1.0
    # corr(fav-oriented margin resid, total resid) = rho  ->  corr(M, T) = rho * fav_sign
    z = (M - mu_m) / max(sd_m, 1e-6)
    T = pred_total + sigma_total * (rho_fav * fav_sign * z + np.sqrt(max(1 - rho_fav ** 2, 0.0)) * rng.standard_normal(n))
    T = np.maximum(np.round(T), np.abs(M) + 3)  # the loser scores >= 0 (and some points happen)
    # integer points with the right parity
    T = np.where((T + M) % 2 == 1, T + 1, T)
    hp, ap = (T + M) / 2, (T - M) / 2
    stats: dict[tuple[str, str], np.ndarray] = {}

    for team, pts, opp_pts, exp_pts, exp_opp in ((home, hp, ap, (pred_total + mu_m) / 2, (pred_total - mu_m) / 2),
                                                  (away, ap, hp, (pred_total - mu_m) / 2, (pred_total + mu_m) / 2)):
        plays = team.plays + PLAYS_PER_TOTAL_POINT * (T - pred_total) / 2 + rng.normal(0, 4.5, n)
        plays = np.clip(np.round(plays), 40, 90).astype(int)
        script = (opp_pts - exp_opp) - (pts - exp_pts)  # >0 when trailing more than expected
        pr = np.clip(team.pass_rate + PASS_RATE_PER_POINT * script, 0.35, 0.8)
        dropbacks = rng.binomial(plays, pr)
        rush_att = plays - dropbacks
        # sacks, throwaways and spikes use a dropback but produce no target
        pass_att = rng.binomial(dropbacks, TARGETS_PER_DROPBACK)
        pts_z = (pts - exp_pts) / 7.0
        eff_pass = np.exp(EFF_SD * (0.6 * pts_z + 0.8 * rng.standard_normal(n)))
        eff_rush = np.exp(0.8 * EFF_SD * (0.5 * pts_z + 0.85 * rng.standard_normal(n)))

        rec_players = [p for p in team.players if p.target_share > 0]
        shares = np.array([p.target_share for p in rec_players] + [max(0.0, 1 - sum(p.target_share for p in rec_players))])
        shares = shares / shares.sum()
        targets = rng.multinomial(pass_att, shares) if len(shares) > 1 else pass_att[:, None]
        team_pass_yds = np.zeros(n)
        team_cmp = np.zeros(n)
        for j, pl in enumerate(rec_players):
            t = targets[:, j]
            rec = rng.binomial(t, pl.catch_rate)
            shape = 1.3
            yds = np.where(rec > 0, rng.gamma(np.maximum(rec, 1) * shape, pl.ypr * eff_pass / shape), 0.0)
            yds = np.round(yds)
            stats[(pl.player, "receptions")] = rec
            stats[(pl.player, "rec_yds")] = yds
            team_pass_yds += yds
            team_cmp += rec
        # unprojected receivers
        t_other = targets[:, -1]
        rec_o = rng.binomial(t_other, 0.64)
        team_pass_yds += np.where(rec_o > 0, np.round(rng.gamma(np.maximum(rec_o, 1) * 1.3, 11.0 * eff_pass / 1.3)), 0.0)
        team_cmp += rec_o

        # QB scrambles: a dropback that ends as a QB carry in the box score
        scrambles = rng.binomial(dropbacks, SCRAMBLE_RATE) if team.passer is not None else np.zeros(n, dtype=int)
        rush_players = [p for p in team.players if p.carry_share > 0]
        cshares = np.array([p.carry_share for p in rush_players] + [max(0.0, 1 - sum(p.carry_share for p in rush_players))])
        cshares = cshares / cshares.sum()
        carries = rng.multinomial(rush_att, cshares) if len(cshares) > 1 else rush_att[:, None]
        for j, pl in enumerate(rush_players):
            c = carries[:, j]
            yds = np.round(c * pl.ypc * eff_rush + np.sqrt(c) * 5.2 * rng.standard_normal(n))
            if team.passer is not None and pl.player == team.passer.player:
                c = c + scrambles
                yds = yds + np.round(scrambles * 6.5 * eff_pass + np.sqrt(scrambles) * 5.0 * rng.standard_normal(n))
            stats[(pl.player, "rush_att")] = c
            stats[(pl.player, "rush_yds")] = yds

        # touchdowns
        n_td = rng.poisson(np.maximum(pts, 0) * TD_PER_POINT)
        n_rush_td = rng.binomial(n_td, team.rush_td_frac)
        n_rec_td = n_td - n_rush_td
        rec_td_sh = np.array([p.rec_td_share for p in rec_players] + [max(0.05, 1 - sum(p.rec_td_share for p in rec_players))])
        rush_td_sh = np.array([p.rush_td_share for p in rush_players] + [max(0.05, 1 - sum(p.rush_td_share for p in rush_players))])
        rec_tds = rng.multinomial(n_rec_td, rec_td_sh / rec_td_sh.sum())
        rush_tds = rng.multinomial(n_rush_td, rush_td_sh / rush_td_sh.sum())
        any_td: dict[str, np.ndarray] = {}
        for j, pl in enumerate(rec_players):
            any_td[pl.player] = any_td.get(pl.player, 0) + rec_tds[:, j]
        for j, pl in enumerate(rush_players):
            any_td[pl.player] = any_td.get(pl.player, 0) + rush_tds[:, j]
        for name, arr in any_td.items():
            stats[(name, "anytime_td")] = arr
        for pl in team.players:
            r_y, c_y = stats.get((pl.player, "rec_yds")), stats.get((pl.player, "rush_yds"))
            if r_y is not None or c_y is not None:
                stats[(pl.player, "rush_rec_yds")] = (r_y if r_y is not None else 0) + (c_y if c_y is not None else 0)

        if team.passer is not None:
            q = team.passer.player
            stats[(q, "pass_att")] = np.round(dropbacks * ATT_PER_DROPBACK)
            stats[(q, "pass_cmp")] = team_cmp
            stats[(q, "pass_yds")] = team_pass_yds
            stats[(q, "pass_td")] = n_rec_td
            stats[(q, "pass_int")] = rng.poisson(0.024 * pass_att / np.clip(eff_pass, 0.6, 1.6))
            ry = stats.get((q, "rush_yds"))
            stats[(q, "pass_rush_yds")] = team_pass_yds + (ry if ry is not None else 0)

    return GameSim(n=n, margin=M, total=T, home_pts=hp, away_pts=ap, stats=stats)

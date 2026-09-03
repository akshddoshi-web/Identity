"""Elo / power-rating baseline model.

This is deliberately the *sanity-check benchmark*, not the primary model: if
the gradient-boosted model can't beat a simple Elo rating out-of-sample, the
extra complexity isn't earning its keep and the "edge" it finds is probably
noise. Elo is also useful standalone as a prior / feature into the GBM.

Margin-of-victory (MOV) multiplier follows the FiveThirtyEight NFL Elo
approach (log(abs(margin)+1) * (2.2 / (elo_diff*0.001 + 2.2))), generalized
to NCAAF and NBA with sport-specific K and home-advantage from config.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

DEFAULT_RATING = 1500.0


@dataclass
class EloModel:
    k: float = 20.0
    home_advantage: float = 55.0
    mov_multiplier: bool = True
    ratings: dict[str, float] = field(default_factory=dict)

    def get_rating(self, team: str) -> float:
        return self.ratings.get(team, DEFAULT_RATING)

    def win_probability(self, home_team: str, away_team: str, neutral_site: bool = False) -> float:
        home_r = self.get_rating(home_team) + (0.0 if neutral_site else self.home_advantage)
        away_r = self.get_rating(away_team)
        return 1.0 / (1.0 + 10 ** ((away_r - home_r) / 400.0))

    def expected_margin_proxy(self, home_team: str, away_team: str, neutral_site: bool = False) -> float:
        """Not a calibrated point-margin prediction — a monotonic proxy (Elo
        diff / 25, the common football rule-of-thumb of ~25 Elo points per
        point of margin) useful as a GBM feature, not as a standalone total
        prediction. The GBM's margin model is what should be trusted for an
        actual spread comparison.
        """
        home_r = self.get_rating(home_team) + (0.0 if neutral_site else self.home_advantage)
        away_r = self.get_rating(away_team)
        return (home_r - away_r) / 25.0

    def update(self, home_team: str, away_team: str, home_score: int, away_score: int, neutral_site: bool = False) -> None:
        home_r = self.get_rating(home_team)
        away_r = self.get_rating(away_team)
        prob_home = self.win_probability(home_team, away_team, neutral_site)

        if home_score > away_score:
            actual_home = 1.0
        elif home_score < away_score:
            actual_home = 0.0
        else:
            actual_home = 0.5

        k_eff = self.k
        if self.mov_multiplier and home_score != away_score:
            margin = abs(home_score - away_score)
            elo_diff = (home_r + (0 if neutral_site else self.home_advantage)) - away_r
            # winner-relative elo diff, so the multiplier compresses upsets-by-a-lot
            winner_elo_diff = elo_diff if actual_home == 1.0 else -elo_diff
            mult = math.log(margin + 1) * (2.2 / (winner_elo_diff * 0.001 + 2.2))
            mult = max(mult, 0.1)  # guard against pathological negative/zero multipliers
            k_eff = self.k * mult

        delta = k_eff * (actual_home - prob_home)
        self.ratings[home_team] = home_r + delta
        self.ratings[away_team] = away_r - delta

    def process_games_chronological(self, games: list[dict]) -> None:
        """`games`: list of dicts with keys home_team, away_team, home_score,
        away_score, neutral_site, sorted ascending by date already. Mutates
        self.ratings in place, one update per completed game.
        """
        for g in games:
            if g.get("home_score") is None or g.get("away_score") is None:
                continue
            self.update(
                g["home_team"],
                g["away_team"],
                g["home_score"],
                g["away_score"],
                g.get("neutral_site", False),
            )

    def snapshot(self) -> dict[str, float]:
        return dict(self.ratings)


def build_elo_for_sport(sport: str, cfg: dict) -> EloModel:
    sport_cfg = cfg["sports"][sport]
    return EloModel(k=sport_cfg["elo_k"], home_advantage=sport_cfg["elo_home_advantage"])

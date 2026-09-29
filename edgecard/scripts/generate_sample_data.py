"""Generates synthetic historical data across NFL, NCAAF, and NBA so the rest
of the pipeline (feature engineering, walk-forward backtesting, de-vigging,
edge detection, CLV, Kelly sizing, dashboard) can be exercised end-to-end
without any real data source or API key.

IMPORTANT: this data is fabricated. Team "true ratings" drift randomly
season to season, game outcomes are drawn from those ratings plus noise, and
the synthetic "market" lines are built from the same true ratings plus a
different noise draw. Any "edge" the models appear to find against this
synthetic market is an artifact of how the generator works, NOT evidence the
modeling approach works on real markets. This script exists purely to
validate that the pipeline runs correctly end to end (schema, walk-forward
mechanics, de-vig math, Kelly sizing, dashboard rendering) — never point
`scripts/run_pipeline_demo.py`'s output at this data and call it a backtest
of real edge.
"""
from __future__ import annotations

import datetime as dt
import math
import random

import numpy as np

from data_pipeline.db import connect, init_db
from data_pipeline.schema import GameRecord, OddsSnapshot, TeamGameStats
from data_pipeline.ingest_games import upsert_games
from data_pipeline.ingest_advanced_stats import upsert_team_game_stats
from data_pipeline.ingest_odds import store_odds_snapshots
from edge.devig import decimal_to_american

SEED = 42

SPORT_CONFIG = {
    "NFL": dict(n_teams=32, seasons=list(range(2016, 2024)), games_per_team=17, home_adv=2.0, margin_sigma=13.5),
    "NCAAF": dict(n_teams=28, seasons=list(range(2016, 2024)), games_per_team=12, home_adv=2.5, margin_sigma=17.0),
    "NBA": dict(n_teams=30, seasons=list(range(2019, 2024)), games_per_team=60, home_adv=2.8, margin_sigma=12.0),
}


def american_from_prob(prob: float) -> float:
    prob = min(max(prob, 0.02), 0.98)
    decimal_odds = 1.0 / prob
    return round(decimal_to_american(decimal_odds))


def two_sided_prices(prob_a: float, total_vig: float = 0.045) -> tuple[float, float]:
    p_a_raw, p_b_raw = prob_a, 1 - prob_a
    scale = 1 + total_vig
    return american_from_prob(p_a_raw * scale), american_from_prob(p_b_raw * scale)


def build_teams(sport: str, n_teams: int, rng: random.Random) -> list[str]:
    return [f"{sport}_Team_{i:02d}" for i in range(1, n_teams + 1)]


def generate_sport(sport: str, cfg: dict, rng: random.Random, np_rng: np.random.Generator):
    n_teams = cfg["n_teams"]
    teams = build_teams(sport, n_teams, rng)
    is_dome = {t: rng.random() < 0.25 for t in teams}
    home_coords = {t: (rng.uniform(25, 48), rng.uniform(-122, -71)) for t in teams}

    true_rating = {t: np_rng.normal(0, 10) for t in teams}

    games: list[GameRecord] = []
    stats_rows: list[TeamGameStats] = []
    odds_rows: list[OddsSnapshot] = []

    last_played: dict[str, dt.date] = {t: None for t in teams}

    for season in cfg["seasons"]:
        # season-to-season drift so ratings aren't static across 8-10 years
        for t in teams:
            true_rating[t] += np_rng.normal(0, 4)

        season_start = dt.date(season, 9, 1) if sport in ("NFL", "NCAAF") else dt.date(season, 10, 20)
        games_per_team = cfg["games_per_team"]
        n_weeks = games_per_team if sport != "NBA" else games_per_team  # simplified: one game-slate per "week unit"

        schedule_teams = teams[:]
        for week in range(n_weeks):
            rng.shuffle(schedule_teams)
            game_date = season_start + dt.timedelta(days=7 * week if sport != "NBA" else 3 * week)
            pairs = list(zip(schedule_teams[0::2], schedule_teams[1::2]))
            for home, away in pairs:
                game_id = f"{sport}_{season}_{week:02d}_{home}_{away}"

                home_r = true_rating[home] + cfg["home_adv"]
                away_r = true_rating[away]
                margin_mean = home_r - away_r
                margin = np_rng.normal(margin_mean, cfg["margin_sigma"])
                margin = round(margin)

                base_total = 44 if sport == "NFL" else (52 if sport == "NCAAF" else 220)
                total_points = max(0, round(base_total + np_rng.normal(0, base_total * 0.12)))
                home_score = round((total_points + margin) / 2)
                away_score = total_points - home_score
                if home_score == away_score:
                    home_score += 1  # no ties in the synthetic data, keeps downstream math simple

                home_rest = (game_date - last_played[home]).days if last_played[home] else 10
                away_rest = (game_date - last_played[away]).days if last_played[away] else 10
                last_played[home] = game_date
                last_played[away] = game_date

                hx, hy = home_coords[home]
                ax, ay = home_coords[away]
                travel_mi = round(69.0 * math.hypot(hx - ax, hy - ay), 1)  # rough degrees->miles

                dome = is_dome[home]
                weather_temp = None
                weather_wind = None
                weather_precip = None
                if sport in ("NFL", "NCAAF") and not dome:
                    weather_temp = round(np_rng.normal(55, 20), 1)
                    weather_wind = round(abs(np_rng.normal(8, 5)), 1)
                    weather_precip = rng.choices(["none", "rain", "snow"], weights=[0.75, 0.18, 0.07])[0]

                games.append(
                    GameRecord(
                        game_id=game_id,
                        sport=sport,
                        season=season,
                        week=week + 1 if sport != "NBA" else None,
                        game_date=game_date.isoformat(),
                        home_team=home,
                        away_team=away,
                        home_score=int(home_score),
                        away_score=int(away_score),
                        is_final=True,
                        neutral_site=False,
                        home_rest_days=home_rest,
                        away_rest_days=away_rest,
                        home_travel_mi=0.0,
                        away_travel_mi=travel_mi,
                        referee_crew=f"Crew_{rng.randint(1, 17):02d}",
                        weather_temp_f=weather_temp,
                        weather_wind_mph=weather_wind,
                        weather_precip=weather_precip,
                        is_dome=dome,
                    )
                )

                stats_rows.extend(_synthetic_stats(sport, game_id, home, away, home_score, away_score, np_rng))
                odds_rows.extend(_synthetic_odds(sport, game_id, margin_mean, cfg["margin_sigma"], total_points, base_total, game_date, np_rng))

    return games, stats_rows, odds_rows


def _synthetic_stats(sport, game_id, home, away, home_score, away_score, np_rng) -> list[TeamGameStats]:
    rows = []
    for team, is_home, own_score, opp_score in (
        (home, True, home_score, away_score),
        (away, False, away_score, home_score),
    ):
        perf = (own_score - opp_score) / 20.0
        if sport in ("NFL", "NCAAF"):
            rows.append(
                TeamGameStats(
                    game_id=game_id,
                    team=team,
                    is_home=is_home,
                    epa_per_play=round(float(np_rng.normal(0.02 + 0.05 * perf, 0.08)), 4),
                    success_rate=round(float(np.clip(np_rng.normal(0.45 + 0.03 * perf, 0.05), 0.2, 0.75)), 4),
                    pass_epa_per_play=round(float(np_rng.normal(0.05 + 0.05 * perf, 0.1)), 4),
                    rush_epa_per_play=round(float(np_rng.normal(-0.02 + 0.03 * perf, 0.08)), 4),
                    red_zone_pct=round(float(np.clip(np_rng.normal(0.55 + 0.04 * perf, 0.12), 0.1, 0.95)), 4),
                    third_down_pct=round(float(np.clip(np_rng.normal(0.40 + 0.03 * perf, 0.08), 0.1, 0.75)), 4),
                    pressure_rate=round(float(np.clip(np_rng.normal(0.25 - 0.02 * perf, 0.06), 0.05, 0.55)), 4),
                )
            )
        else:
            rows.append(
                TeamGameStats(
                    game_id=game_id,
                    team=team,
                    is_home=is_home,
                    off_rating=round(float(np_rng.normal(112 + 3 * perf, 6)), 2),
                    def_rating=round(float(np_rng.normal(112 - 3 * perf, 6)), 2),
                    pace=round(float(np_rng.normal(99, 4)), 2),
                    efg_pct=round(float(np.clip(np_rng.normal(0.53 + 0.02 * perf, 0.03), 0.4, 0.65)), 4),
                    tov_pct=round(float(np.clip(np_rng.normal(0.13 - 0.005 * perf, 0.02), 0.08, 0.2)), 4),
                    orb_pct=round(float(np.clip(np_rng.normal(0.23 + 0.01 * perf, 0.04), 0.1, 0.4)), 4),
                    ftr=round(float(np.clip(np_rng.normal(0.22, 0.05), 0.05, 0.45)), 4),
                    net_rating_lineup_wtd=round(float(np_rng.normal(3 * perf, 4)), 2),
                )
            )
    return rows


def _synthetic_odds(sport, game_id, margin_mean, margin_sigma, total_points, base_total, game_date, np_rng) -> list[OddsSnapshot]:
    from scipy.stats import norm

    rows = []
    open_captured = (dt.datetime.combine(game_date, dt.time(9, 0)) - dt.timedelta(days=4)).isoformat()
    close_captured = (dt.datetime.combine(game_date, dt.time(17, 0))).isoformat()

    # opening line: noisier estimate of true margin_mean; closing line: tighter
    open_margin_est = margin_mean + np_rng.normal(0, margin_sigma * 0.35)
    close_margin_est = margin_mean + np_rng.normal(0, margin_sigma * 0.12)

    for snapshot_type, margin_est, captured_at in (("open", open_margin_est, open_captured), ("close", close_margin_est, close_captured)):
        prob_home_cover_pk = norm.cdf(margin_est / margin_sigma)  # prob home wins straight up, reused as ML prob
        home_price, away_price = two_sided_prices(prob_home_cover_pk)
        home_point = -round(margin_est * 2) / 2  # spread expressed as home line (negative = home favored)
        rows.append(
            OddsSnapshot(
                game_id=game_id, book="synthetic_book", snapshot_type=snapshot_type, captured_at=captured_at,
                market="moneyline", home_price=home_price, away_price=away_price,
            )
        )
        rows.append(
            OddsSnapshot(
                game_id=game_id, book="synthetic_book", snapshot_type=snapshot_type, captured_at=captured_at,
                market="spread", home_price=-110, away_price=-110, home_point=home_point, away_point=-home_point,
            )
        )

    open_total_est = total_points + np_rng.normal(0, base_total * 0.06)
    close_total_est = total_points + np_rng.normal(0, base_total * 0.02)
    for snapshot_type, total_est, captured_at in (("open", open_total_est, open_captured), ("close", close_total_est, close_captured)):
        rows.append(
            OddsSnapshot(
                game_id=game_id, book="synthetic_book", snapshot_type=snapshot_type, captured_at=captured_at,
                market="total", home_price=-110, away_price=-110,
                home_point=round(total_est * 2) / 2, away_point=round(total_est * 2) / 2,
            )
        )
    return rows


def main():
    rng = random.Random(SEED)
    np_rng = np.random.default_rng(SEED)

    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM odds_snapshots")
        conn.execute("DELETE FROM clv_records")
        conn.execute("DELETE FROM bet_ledger")
        conn.execute("DELETE FROM predictions")
        conn.execute("DELETE FROM team_game_stats")
        conn.execute("DELETE FROM injuries")
        conn.execute("DELETE FROM games")

        for sport, cfg in SPORT_CONFIG.items():
            print(f"Generating synthetic {sport} data: {len(cfg['seasons'])} seasons, {cfg['n_teams']} teams...")
            games, stats_rows, odds_rows = generate_sport(sport, cfg, rng, np_rng)
            upsert_games(games, conn)
            upsert_team_game_stats(stats_rows, conn)
            store_odds_snapshots(odds_rows, conn)
            print(f"  {sport}: {len(games)} games, {len(stats_rows)} team-game-stat rows, {len(odds_rows)} odds rows")

    print("Synthetic data generation complete. This data is FAKE — see module docstring.")


if __name__ == "__main__":
    main()

"""Point-in-time NFL game features.

Every feature for game G is computed from information available before G
kicks off:
  - team form: exponentially weighted averages over the team's PREVIOUS
    games only, opponent-adjusted using the opponent's PRE-game rating, and
    regressed toward the league mean at each new season;
  - Elo: pre-game rating (updated only after each game);
  - schedule/travel: data_pipeline/schedule_features (schedule is public);
  - situational proxies: built from prior games, the published schedule,
    starting QB (announced before kickoff), coach, trades dated before G;
  - weather: game-time conditions (historical: nflverse; live: Open-Meteo
    forecast for the kickoff hour).
Targets (margin, total) and closing prices are carried as separate columns
and are never inputs to the feature computation. tests/test_leakage.py
verifies that changing a game's result cannot change that game's features.

Features are grouped so the backtest can test each situational hypothesis
separately (FEATURE_GROUPS).
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import pandas as pd

from data_pipeline.schedule_features import game_level_schedule_features
from data_pipeline.venues import is_weather_exposed

HALF_LIFE_GAMES = 6.0
SEASON_CARRYOVER = 0.6  # share of last season's form kept at week 1

FORM_STATS = [
    "epa_play", "def_epa_play", "success_rate", "def_success_rate", "pass_epa", "def_pass_epa",
    "rush_epa", "def_rush_epa", "pressure_rate_allowed", "def_pressure_rate_allowed", "rz_td_rate",
    "def_rz_td_rate", "st_epa", "plays", "proe", "fumble_luck", "turnover_margin", "points_for",
    "points_against", "sack_rate", "def_sack_rate",
]

# Pre-data priors for league-average team-game stats (roughly the 2010s NFL).
LEAGUE_PRIORS: dict[str, float] = {
    "epa_play": 0.0, "def_epa_play": 0.0, "success_rate": 0.43, "def_success_rate": 0.43, "pass_epa": 0.03,
    "def_pass_epa": 0.03, "rush_epa": -0.05, "def_rush_epa": -0.05, "pressure_rate_allowed": 0.15,
    "def_pressure_rate_allowed": 0.15, "rz_td_rate": 0.6, "def_rz_td_rate": 0.6, "st_epa": 0.0, "plays": 62.0,
    "proe": 0.0, "fumble_luck": 0.0, "turnover_margin": 0.0, "points_for": 22.0, "points_against": 22.0,
    "sack_rate": 0.065, "def_sack_rate": 0.065, "adj_off": 0.0, "adj_def": 0.0,
}

FEATURE_GROUPS: dict[str, list[str]] = {
    "base": [
        "elo_diff", "elo_prob", "home_field",
        "f_net_epa_diff", "f_off_epa_h_vs_def_a", "f_off_epa_a_vs_def_h", "f_success_diff",
        "f_pass_epa_diff", "f_rush_epa_diff", "f_points_diff", "f_pace_sum", "f_off_epa_sum", "f_def_epa_sum",
        "f_points_for_sum",
    ],
    "opp_adjusted": ["f_adj_net_epa_diff", "f_adj_off_sum"],
    "pressure_redzone": ["f_pressure_mismatch_h", "f_pressure_mismatch_a", "f_rz_diff"],
    "special_teams": ["f_st_epa_diff"],
    "turnover_luck": ["f_fumble_luck_diff", "f_turnover_margin_diff"],
    "fatigue": ["sched_rest_diff", "sched_short_week_diff", "sched_travel_diff", "sched_tz_away_abs",
                "sched_prev_ot_diff", "post_bye_diff", "west_to_east_early"],
    "cohesion": ["qb_change_h", "qb_change_a", "qb_new_starts_h", "qb_new_starts_a", "trades_recent_h",
                 "trades_recent_a", "new_usage_overlap_h", "new_usage_overlap_a"],
    "motivation": ["div_game", "playoff_game", "elim_proxy_h", "elim_proxy_a", "revenge_h", "revenge_a",
                   "new_coach_h", "new_coach_a", "letdown_h", "letdown_a", "lookahead_h", "lookahead_a"],
    "weather": ["wx_wind", "wx_temp_cold", "wx_outdoor"],
    "h2h": ["h2h_resid_margin"],
    "altitude": ["sched_altitude_ft"],
}


def all_feature_cols(groups: list[str] | None = None) -> list[str]:
    groups = groups or list(FEATURE_GROUPS)
    cols: list[str] = []
    for g in groups:
        cols += FEATURE_GROUPS[g]
    return cols


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def prepare_games(games: pd.DataFrame, min_season: int = 2012) -> pd.DataFrame:
    g = games[games["season"] >= min_season].copy()
    g["kickoff"] = pd.to_datetime(g["gameday"].astype(str) + " " + g["gametime"].fillna("13:00").astype(str),
                                  errors="coerce")
    g["game_date"] = g["gameday"].astype(str)
    g = g.sort_values(["kickoff", "game_id"]).reset_index(drop=True)
    g["margin"] = g["home_score"] - g["away_score"]
    g["total_pts"] = g["home_score"] + g["away_score"]
    g["is_final"] = g["home_score"].notna() & g["away_score"].notna()
    g["neutral_site"] = (g.get("location", "Home") == "Neutral").astype(int)
    return g


class _EWMA:
    """Per-team exponentially weighted state with season regression."""

    def __init__(self, stats: list[str], half_life: float):
        self.alpha = 1 - 0.5 ** (1 / half_life)
        self.stats = stats
        self.state: dict[str, dict[str, float]] = {}
        self.season: dict[str, int] = {}
        self.n: dict[str, int] = defaultdict(int)

    def get(self, team: str, season: int, league_mean: dict[str, float]) -> dict[str, float]:
        if team not in self.state:
            return dict(league_mean)
        for k, v in league_mean.items():  # stats a team has never had a value for
            self.state[team].setdefault(k, v)
        if self.season.get(team) != season:
            # regress once at the season boundary
            self.state[team] = {k: SEASON_CARRYOVER * v + (1 - SEASON_CARRYOVER) * league_mean.get(k, v)
                                for k, v in self.state[team].items()}
            self.season[team] = season
        return dict(self.state[team])

    def update(self, team: str, season: int, obs: dict[str, float]) -> None:
        cur = self.state.get(team)
        if cur is None:
            self.state[team] = {k: v for k, v in obs.items() if v is not None and not math.isnan(v)}
        else:
            for k, v in obs.items():
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    continue
                cur[k] = cur.get(k, v) + self.alpha * (v - cur.get(k, v))
        self.season[team] = season
        self.n[team] += 1


# --------------------------------------------------------------------------- #
# main builder
# --------------------------------------------------------------------------- #

def build_nfl_features(
    games: pd.DataFrame,
    team_games: pd.DataFrame,
    trades: pd.DataFrame | None = None,
    player_weeks: pd.DataFrame | None = None,
    elo_k: float = 20.0,
    elo_hfa: float = 48.0,
) -> pd.DataFrame:
    """games: nflverse games.csv rows (may include unplayed future games —
    they get features but no targets). Returns one row per game."""
    g = prepare_games(games)
    tg = team_games.set_index(["game_id", "team"])
    # League means must be point-in-time too: start from fixed priors and
    # update only with games already played (a global mean over all seasons
    # would leak future seasons into week-1 features — tests/test_leakage.py).
    league_mean = dict(LEAGUE_PRIORS)
    league_n = 0

    form = _EWMA(FORM_STATS + ["adj_off", "adj_def"], HALF_LIFE_GAMES)
    elo: dict[str, float] = defaultdict(lambda: 1500.0)
    elo_season: dict[str, int] = {}

    last_qb: dict[str, str] = {}
    qb_starts: dict[str, int] = defaultdict(int)
    coach_season: dict[tuple[str, int], str] = {}
    prev_coach: dict[str, str] = {}
    coach_games: dict[str, int] = defaultdict(int)
    coach_changed: dict[str, bool] = {}
    record: dict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0])
    last_meeting: dict[frozenset, tuple[str, float]] = {}   # pair -> (winner, elo-residual margin from home persp.)
    h2h_resid: dict[tuple[str, str], list[float]] = defaultdict(list)
    last_result: dict[str, tuple[float, float]] = {}  # team -> (margin, opp_elo)

    # trades: date -> receiving team (nflverse trades.csv: trade_date, received ...)
    trade_dates: dict[str, list[pd.Timestamp]] = defaultdict(list)
    if trades is not None and len(trades):
        tcol = "trade_date" if "trade_date" in trades else None
        rcol = "received" if "received" in trades else None
        if tcol and rcol:
            player_trades = trades[trades["pfr_name"].notna()] if "pfr_name" in trades else trades
            for _, r in player_trades.iterrows():
                try:
                    trade_dates[str(r[rcol])].append(pd.Timestamp(r[tcol]))
                except (ValueError, TypeError):
                    continue

    # new high-usage acquisitions: players whose team changed and who carried a
    # large target/rush share on their previous team (from prior weeks only)
    usage_new = _new_usage_players(player_weeks) if player_weeks is not None else {}

    # next-game lookup for lookahead spots (schedule is public in advance)
    next_game: dict[str, dict[str, str | None]] = defaultdict(dict)
    seq: dict[str, list[tuple[pd.Timestamp, str, str]]] = defaultdict(list)
    for _, r in g.iterrows():
        seq[r["home_team"]].append((r["kickoff"], r["game_id"], r["away_team"]))
        seq[r["away_team"]].append((r["kickoff"], r["game_id"], r["home_team"]))
    for team, lst in seq.items():
        lst.sort()
        for i, (_, gid, _) in enumerate(lst):
            next_game[team][gid] = lst[i + 1][2] if i + 1 < len(lst) else None

    rows = []
    for _, r in g.iterrows():
        h, a, s = r["home_team"], r["away_team"], int(r["season"])
        for t in (h, a):
            if elo_season.get(t) is not None and elo_season[t] != s:
                elo[t] = 0.67 * elo[t] + 0.33 * 1500.0
            elo_season[t] = s
        fh, fa = form.get(h, s, league_mean), form.get(a, s, league_mean)
        hfa = 0.0 if r["neutral_site"] else elo_hfa
        elo_diff = elo[h] + hfa - elo[a]
        elo_prob = 1 / (1 + 10 ** (-elo_diff / 400))

        # --- cohesion
        hq, aq = r.get("home_qb_id"), r.get("away_qb_id")
        qb_change_h = float(h in last_qb and pd.notna(hq) and last_qb[h] != hq)
        qb_change_a = float(a in last_qb and pd.notna(aq) and last_qb[a] != aq)
        kick = r["kickoff"]
        trades_h = sum(1 for d in trade_dates.get(h, []) if pd.Timedelta(0) < kick - d <= pd.Timedelta(days=35))
        trades_a = sum(1 for d in trade_dates.get(a, []) if pd.Timedelta(0) < kick - d <= pd.Timedelta(days=35))

        # --- motivation
        wh, lh = record[(h, s)]
        wa, la = record[(a, s)]
        wk = int(r["week"]) if pd.notna(r["week"]) else 0
        is_reg = r.get("game_type", "REG") == "REG"
        elim_h = float(is_reg and wk >= 13 and (wh + lh) > 0 and wh / (wh + lh) <= 0.3)
        elim_a = float(is_reg and wk >= 13 and (wa + la) > 0 and wa / (wa + la) <= 0.3)
        pair = frozenset((h, a))
        lm = last_meeting.get(pair)
        revenge_h = float(lm is not None and lm[0] == a)
        revenge_a = float(lm is not None and lm[0] == h)
        def _new_coach(team, coach):
            # games already coached for this team by tonight's coach (0 if he's new tonight)
            if prev_coach.get(team) is None:
                return 0.0
            n_with = 0 if coach != prev_coach[team] else coach_games[team]
            return float(n_with < 4 and coach_changed.get(team, coach != prev_coach[team]))

        new_coach_h = _new_coach(h, r.get("home_coach"))
        new_coach_a = _new_coach(a, r.get("away_coach"))
        # letdown: coming off a win over a strong (Elo>=1600) opponent
        lr_h, lr_a = last_result.get(h), last_result.get(a)
        letdown_h = float(lr_h is not None and lr_h[0] > 0 and lr_h[1] >= 1600)
        letdown_a = float(lr_a is not None and lr_a[0] > 0 and lr_a[1] >= 1600)
        nh, na = next_game[h].get(r["game_id"]), next_game[a].get(r["game_id"])
        lookahead_h = float(nh is not None and elo[nh] >= 1600 and elo[a] < 1480)
        lookahead_a = float(na is not None and elo[na] >= 1600 and elo[h] < 1480)
        h2h = h2h_resid.get((h, a), []) + [-x for x in h2h_resid.get((a, h), [])]

        # --- weather
        outdoor = float(str(r.get("roof", "")).lower() in ("outdoors", "open"))
        wind = float(r["wind"]) if pd.notna(r.get("wind")) else (0.0 if not outdoor else np.nan)
        temp = float(r["temp"]) if pd.notna(r.get("temp")) else np.nan

        row = {
            "game_id": r["game_id"], "season": s, "week": wk, "game_type": r.get("game_type"),
            "kickoff": kick, "game_date": r["game_date"], "home_team": h, "away_team": a,
            "neutral_site": r["neutral_site"], "home_field": 0.0 if r["neutral_site"] else 1.0,
            "elo_home": elo[h], "elo_away": elo[a], "elo_diff": elo_diff, "elo_prob": elo_prob,
            # form differentials
            "f_net_epa_diff": (fh["epa_play"] - fh["def_epa_play"]) - (fa["epa_play"] - fa["def_epa_play"]),
            "f_off_epa_h_vs_def_a": fh["epa_play"] + fa["def_epa_play"],
            "f_off_epa_a_vs_def_h": fa["epa_play"] + fh["def_epa_play"],
            "f_success_diff": (fh["success_rate"] - fh["def_success_rate"]) - (fa["success_rate"] - fa["def_success_rate"]),
            "f_pass_epa_diff": (fh["pass_epa"] - fh["def_pass_epa"]) - (fa["pass_epa"] - fa["def_pass_epa"]),
            "f_rush_epa_diff": (fh["rush_epa"] - fh["def_rush_epa"]) - (fa["rush_epa"] - fa["def_rush_epa"]),
            "f_points_diff": (fh["points_for"] - fh["points_against"]) - (fa["points_for"] - fa["points_against"]),
            "f_pace_sum": fh["plays"] + fa["plays"],
            "f_off_epa_sum": fh["epa_play"] + fa["epa_play"],
            "f_def_epa_sum": fh["def_epa_play"] + fa["def_epa_play"],
            "f_points_for_sum": fh["points_for"] + fa["points_for"] + fh["points_against"] + fa["points_against"],
            "f_adj_net_epa_diff": (fh["adj_off"] - fh["adj_def"]) - (fa["adj_off"] - fa["adj_def"]),
            "f_adj_off_sum": fh["adj_off"] + fa["adj_off"] + fh["adj_def"] + fa["adj_def"],
            "f_pressure_mismatch_h": fa["def_pressure_rate_allowed"] - fh["pressure_rate_allowed"],
            "f_pressure_mismatch_a": fh["def_pressure_rate_allowed"] - fa["pressure_rate_allowed"],
            "f_rz_diff": (fh["rz_td_rate"] - fh["def_rz_td_rate"]) - (fa["rz_td_rate"] - fa["def_rz_td_rate"]),
            "f_st_epa_diff": fh["st_epa"] - fa["st_epa"],
            "f_fumble_luck_diff": fh["fumble_luck"] - fa["fumble_luck"],
            "f_turnover_margin_diff": fh["turnover_margin"] - fa["turnover_margin"],
            # cohesion
            "qb_change_h": qb_change_h, "qb_change_a": qb_change_a,
            "qb_new_starts_h": float(min(qb_starts[h], 8)) if qb_change_h or qb_starts[h] < 8 else 8.0,
            "qb_new_starts_a": float(min(qb_starts[a], 8)) if qb_change_a or qb_starts[a] < 8 else 8.0,
            "trades_recent_h": float(trades_h), "trades_recent_a": float(trades_a),
            "new_usage_overlap_h": float(usage_new.get((h, r["game_id"]), 0)),
            "new_usage_overlap_a": float(usage_new.get((a, r["game_id"]), 0)),
            # motivation
            "div_game": float(r.get("div_game", 0) or 0), "playoff_game": float(not is_reg),
            "elim_proxy_h": elim_h, "elim_proxy_a": elim_a, "revenge_h": revenge_h, "revenge_a": revenge_a,
            "new_coach_h": new_coach_h, "new_coach_a": new_coach_a, "letdown_h": letdown_h, "letdown_a": letdown_a,
            "lookahead_h": lookahead_h, "lookahead_a": lookahead_a,
            # weather
            "wx_wind": wind, "wx_temp_cold": float(max(0.0, 40.0 - temp)) if not np.isnan(temp) else (0.0 if not outdoor else np.nan),
            "wx_outdoor": outdoor,
            # h2h: recency-weighted Elo residual of previous meetings (home persp.)
            "h2h_resid_margin": float(np.average(h2h[-3:], weights=np.arange(1, len(h2h[-3:]) + 1))) if h2h else 0.0,
            # market (NOT a model input; used for benchmarking / stacking)
            "spread_line": r.get("spread_line"), "total_line": r.get("total_line"),
            "home_moneyline": r.get("home_moneyline"), "away_moneyline": r.get("away_moneyline"),
            "home_spread_odds": r.get("home_spread_odds"), "away_spread_odds": r.get("away_spread_odds"),
            "over_odds": r.get("over_odds"), "under_odds": r.get("under_odds"),
            # targets
            "margin": r["margin"], "total_pts": r["total_pts"], "is_final": bool(r["is_final"]),
            "home_qb": r.get("home_qb_name"), "away_qb": r.get("away_qb_name"),
            "roof": r.get("roof"), "overtime": r.get("overtime"),
        }
        rows.append(row)

        # ---------------- post-game updates (only after the row is recorded) ------
        if not r["is_final"]:
            continue
        margin = float(r["margin"])
        for team, opp, is_home in ((h, a, 1), (a, h, 0)):
            key = (r["game_id"], team)
            if key in tg.index:
                st = tg.loc[key]
                pf = r["home_score"] if is_home else r["away_score"]
                pa = r["away_score"] if is_home else r["home_score"]
                fo = form.get(opp, s, league_mean)
                obs = {c: float(st[c]) for c in FORM_STATS if c in st.index and pd.notna(st[c])}
                obs.update({
                    "turnover_margin": float(st["takeaways"] - st["giveaways"]),
                    "points_for": float(pf), "points_against": float(pa),
                    "adj_off": float(st["epa_play"] - (fo["def_epa_play"] - league_mean["def_epa_play"])) - league_mean["epa_play"],
                    "adj_def": float(st["def_epa_play"] - (fo["epa_play"] - league_mean["epa_play"])) - league_mean["def_epa_play"],
                })
                form.update(team, s, obs)
                # running league mean (slow EWMA over all team-games played so far)
                league_n += 1
                lr = max(1.0 / league_n, 0.002)
                for k_, v_ in obs.items():
                    if k_ in league_mean and v_ is not None and not (isinstance(v_, float) and math.isnan(v_)):
                        league_mean[k_] += lr * (v_ - league_mean[k_])
        # Elo (538-style MOV multiplier)
        exp_h = elo_prob
        act_h = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
        mult = math.log(abs(margin) + 1) * (2.2 / ((elo_diff if margin > 0 else -elo_diff) * 0.001 + 2.2)) if margin != 0 else 1.0
        delta = elo_k * max(mult, 0.1) * (act_h - exp_h)
        pre_h, pre_a = elo[h], elo[a]
        elo[h] += delta
        elo[a] -= delta
        # bookkeeping for situational features
        for team, qb in ((h, hq), (a, aq)):
            if pd.notna(qb):
                qb_starts[team] = 1 if last_qb.get(team) != qb else qb_starts[team] + 1
                last_qb[team] = qb
        for team, coach in ((h, r.get("home_coach")), (a, r.get("away_coach"))):
            if coach_season.get((team, s)) is None:
                coach_season[(team, s)] = coach
            if prev_coach.get(team) is not None and prev_coach.get(team) != coach:
                coach_games[team] = 0
                coach_changed[team] = True
            elif prev_coach.get(team) is None:
                coach_changed[team] = False
            coach_games[team] += 1
            prev_coach[team] = coach
        if is_reg:
            record[(h, s)][0 if margin > 0 else 1] += 1 if margin != 0 else 0
            record[(a, s)][0 if margin < 0 else 1] += 1 if margin != 0 else 0
        last_meeting[pair] = (h if margin > 0 else a if margin < 0 else "", margin)
        expected = elo_diff / 25.0
        h2h_resid[(h, a)].append(margin - expected)
        last_result[h] = (margin, pre_a)
        last_result[a] = (-margin, pre_h)

    df = pd.DataFrame(rows)
    sched = game_level_schedule_features(
        g[["game_id", "game_date", "home_team", "away_team", "overtime"]].rename(columns={}), "NFL"
    )
    df = df.merge(sched, on="game_id", how="left")
    df["post_bye_diff"] = (df["h_rest_days"] >= 13).astype(float) - (df["a_rest_days"] >= 13).astype(float)
    # west-coast team travelling east for an early (1pm ET) kickoff
    df["west_to_east_early"] = ((df["a_tz_shift"] >= 2) & (df["kickoff"].dt.hour <= 13)).astype(float)
    return df


def _new_usage_players(pw: pd.DataFrame) -> dict[tuple[str, str], int]:
    """Counts, per (team, game), players who joined within the last 6 games
    and had a >=18% target share or >=40% carry share on their previous team
    — the "two high-usage players now share one ball" proxy. Keyed by
    nflverse game_id built from season/week/team (computed lazily by the
    caller's game_id format)."""
    if pw is None or pw.empty or "target_share" not in pw:
        return {}
    d = pw[pw.get("season_type", "REG").isin(["REG", "POST"])] if "season_type" in pw else pw
    d = d.sort_values(["player_id", "season", "week"])
    out: dict[tuple[str, str], int] = defaultdict(int)
    # carry share per team-week
    carries_team = d.groupby(["team", "season", "week"])["carries"].transform("sum").replace(0, np.nan)
    d = d.assign(carry_share=d["carries"] / carries_team)
    for pid, p in d.groupby("player_id"):
        p = p.reset_index(drop=True)
        for i in range(1, len(p)):
            if p.loc[i, "team"] != p.loc[i - 1, "team"]:
                prev = p.iloc[max(0, i - 6):i]
                prev = prev[prev["team"] == p.loc[i - 1, "team"]]
                high = (prev["target_share"].fillna(0).mean() >= 0.18) or (prev["carry_share"].fillna(0).mean() >= 0.40)
                if high:
                    for j in range(i + 1, min(i + 7, len(p))):
                        if p.loc[j, "team"] == p.loc[i, "team"]:
                            out[(p.loc[j, "team"], f"{int(p.loc[j, 'season'])}_{int(p.loc[j, 'week']):02d}")] += 1
    # translate (team, season_week) into the (team, game_id) lookup the builder uses
    return _SeasonWeekLookup(out)


class _SeasonWeekLookup(dict):
    """dict keyed by (team, 'YYYY_WW'); .get((team, game_id)) maps an
    nflverse game_id ('2024_05_KC_NO') onto its season_week prefix. Only
    counts games strictly AFTER the player's first game with the new team,
    so the flag never depends on whether he appeared in the current game."""

    def get(self, key, default=0):  # type: ignore[override]
        team, gid = key
        return super().get((team, str(gid)[:7]), default)

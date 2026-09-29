"""NFL player projections for props: usage share x team volume x efficiency.

Everything is estimated from each player's PREVIOUS games only (EWMA over
recent games with his current team, shrunk toward position priors by
volume), so it is point-in-time. Injury/news adjustments are applied on top
(out = 0, doubtful = 25% of normal usage, questionable = 90%) and the
removed usage is redistributed to teammates at the same position group.

The output (`TeamProjection`) is what sim/nfl_sim.py consumes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

HALF_LIFE = 4.0
POS_PRIORS = {
    # catch rate, yards/target, yards/carry, receiving TD share weight, rushing TD share weight
    "WR": dict(catch=0.63, ypt=7.9, ypc=6.0),
    "TE": dict(catch=0.70, ypt=7.0, ypc=4.0),
    "RB": dict(catch=0.77, ypt=5.6, ypc=4.3),
    "QB": dict(catch=0.60, ypt=6.0, ypc=4.8),
}
PROJECTED_SHARE = 0.95
STATUS_MULT = {"out": 0.0, "doubtful": 0.25, "questionable": 0.9, "probable": 1.0, "active": 1.0}


@dataclass
class PlayerProj:
    player_id: str
    player: str
    position: str
    team: str
    target_share: float
    carry_share: float
    catch_rate: float
    ypt: float            # yards per target (air + YAC, on targets)
    ypc: float            # yards per carry
    rec_td_share: float
    rush_td_share: float
    is_passer: bool = False
    status: str = "active"
    games: int = 0

    @property
    def ypr(self) -> float:  # yards per reception
        return self.ypt / max(self.catch_rate, 0.2)


@dataclass
class TeamProjection:
    team: str
    plays: float
    pass_rate: float
    rush_td_frac: float
    players: list[PlayerProj] = field(default_factory=list)
    passer: PlayerProj | None = None


def _ewma(values: np.ndarray, half_life: float = HALF_LIFE) -> float:
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan
    w = 0.5 ** (np.arange(len(v))[::-1] / half_life)
    return float((w * v).sum() / w.sum())


def team_week_totals(pw: pd.DataFrame) -> pd.DataFrame:
    g = pw.groupby(["team", "season", "week"])
    return pd.DataFrame({
        "team_targets": g["targets"].sum(), "team_carries": g["carries"].sum(),
        "team_pass_att": g["attempts"].sum(), "team_rec_td": g["receiving_tds"].sum(),
        "team_rush_td": g["rushing_tds"].sum(),
    }).reset_index()


def project_team(pw: pd.DataFrame, team: str, before: tuple[int, int], team_plays: float, team_pass_rate: float,
                 statuses: dict[str, str] | None = None, lookback_games: int = 8) -> TeamProjection:
    """pw: player weeks WITH team totals merged (see team_week_totals).
    before: (season, week) of the game being projected; only strictly
    earlier weeks are used."""
    s, w = before
    hist = pw[(pw["team"] == team) & ((pw["season"] < s) | ((pw["season"] == s) & (pw["week"] < w)))]
    # most recent `lookback_games` team-weeks
    weeks = hist[["season", "week"]].drop_duplicates().sort_values(["season", "week"]).tail(lookback_games)
    hist = hist.merge(weeks, on=["season", "week"])
    statuses = {k.lower(): v for k, v in (statuses or {}).items()}
    players: list[PlayerProj] = []
    tot_rush_td = hist.groupby(["season", "week"])["rushing_tds"].sum().sum()
    tot_rec_td = hist.groupby(["season", "week"])["receiving_tds"].sum().sum()
    rush_td_frac = float((tot_rush_td + 4) / (tot_rush_td + tot_rec_td + 10))

    n_weeks = max(len(weeks), 1)
    for pid, p in hist.groupby("player_id"):
        pos = str(p["position"].iloc[-1])
        if pos not in POS_PRIORS:
            continue
        p = weeks.merge(p, on=["season", "week"], how="left")  # absent weeks -> NaN (not zero: may be injured)
        played = p["targets"].notna() | p["carries"].notna()
        if played.sum() == 0:
            continue
        # share when active x how often he's been active lately (a backup who
        # played once at 20% must not keep a 20% share)
        avail = _ewma(played.astype(float).values, 3.0)
        ts = _ewma((p["targets"] / p["team_targets"].replace(0, np.nan)).where(played)) * avail
        cs = _ewma((p["carries"] / p["team_carries"].replace(0, np.nan)).where(played)) * avail
        tgt, rec = p["targets"].sum(), p["receptions"].sum()
        yds_rec, car, yds_rush = p["receiving_yards"].sum(), p["carries"].sum(), p["rushing_yards"].sum()
        pr = POS_PRIORS[pos]
        k_t, k_c = 20.0, 25.0  # prior strength in targets / carries
        catch = (rec + k_t * pr["catch"]) / (tgt + k_t)
        ypt = (yds_rec + k_t * pr["ypt"]) / (tgt + k_t)
        ypc = (yds_rush + k_c * pr["ypc"]) / (car + k_c)
        rec_td_sh = (p["receiving_tds"].sum() + ts * 2) / (tot_rec_td + 2) if tot_rec_td + 2 > 0 else ts
        rush_td_sh = (p["rushing_tds"].sum() + cs * 2) / (tot_rush_td + 2) if tot_rush_td + 2 > 0 else cs
        name = str(p["player"].dropna().iloc[-1])
        status = statuses.get(name.lower(), "active")
        att = p["attempts"].fillna(0)
        is_passer = bool(pos == "QB" and att.tail(3).sum() > 15)
        players.append(PlayerProj(
            player_id=str(pid), player=name, position=pos, team=team,
            target_share=0.0 if np.isnan(ts) else ts, carry_share=0.0 if np.isnan(cs) else cs,
            catch_rate=float(catch), ypt=float(ypt), ypc=float(ypc),
            rec_td_share=float(rec_td_sh), rush_td_share=float(rush_td_sh), is_passer=is_passer,
            status=status, games=int(played.sum()),
        ))
    # recency: drop players who haven't played in the last 3 team-weeks unless listed active by news
    recent = set(hist.merge(weeks.tail(3), on=["season", "week"])["player_id"].astype(str))
    players = [pl for pl in players if pl.player_id in recent or statuses.get(pl.player.lower()) == "active_confirmed"]

    _apply_status_and_renormalize(players)
    passers = [pl for pl in players if pl.is_passer and pl.status not in ("out",)]
    passer = max(passers, key=lambda x: x.games) if passers else None
    return TeamProjection(team=team, plays=team_plays, pass_rate=team_pass_rate, rush_td_frac=rush_td_frac,
                          players=players, passer=passer)


def _apply_status_and_renormalize(players: list[PlayerProj]) -> None:
    """Scale usage by injury status; hand removed usage to healthy players in
    the same position group, pro rata; renormalize so shares sum to <= 1
    (any remainder goes to players we don't project)."""
    for kind in ("target_share", "carry_share"):
        removed_by_pos: dict[str, float] = {}
        for pl in players:
            m = STATUS_MULT.get(pl.status, 1.0)
            cur = getattr(pl, kind)
            removed_by_pos[pl.position] = removed_by_pos.get(pl.position, 0.0) + cur * (1 - m)
            setattr(pl, kind, cur * m)
        for pos, removed in removed_by_pos.items():
            healthy = [pl for pl in players if pl.position == pos and STATUS_MULT.get(pl.status, 1.0) >= 0.9]
            tot = sum(getattr(pl, kind) for pl in healthy)
            if removed > 0 and tot > 0:
                for pl in healthy:
                    setattr(pl, kind, getattr(pl, kind) * (1 + removed / tot))
        # projected players get ~95% of team volume (the rest goes to
        # players without recent usage history); constant tuned on 2025 wk 4-9,
        # validated on 2024 (see reports/backtest_nfl_props.json)
        total = sum(getattr(pl, kind) for pl in players)
        if total > 0:
            scale = PROJECTED_SHARE / total if (total > 1.0 or total < PROJECTED_SHARE) else 1.0
            for pl in players:
                setattr(pl, kind, getattr(pl, kind) * scale)


def team_volume_params(team_games: pd.DataFrame, team: str, before_season: int, before_week: int) -> tuple[float, float]:
    """EWMA plays per game and pass rate for a team from prior games."""
    t = team_games[(team_games["team"] == team) & ((team_games["season"] < before_season) |
                   ((team_games["season"] == before_season) & (team_games["week"] < before_week)))]
    t = t.sort_values(["season", "week"]).tail(10)
    if t.empty:
        return 62.0, 0.58
    return _ewma(t["plays"].values, 5.0), _ewma(t["pass_rate"].values, 5.0)


def statuses_from_injury_report(inj: pd.DataFrame, team: str, season: int, week: int) -> dict[str, str]:
    """Official (Wed-Fri) report for that week: game status if given, else
    'did not participate' Friday-style practice status counts as doubtful.
    This is pre-game information, so using it in the backtest is fair."""
    if inj is None or inj.empty:
        return {}
    d = inj[(inj["team"] == team) & (inj["season"] == season) & (inj["week"] == week)]
    out = {}
    for _, r in d.iterrows():
        st = str(r.get("report_status") or "").lower()
        prac = str(r.get("practice_status") or "").lower()
        if st in ("out", "doubtful", "questionable", "probable"):
            out[str(r["full_name"]).lower()] = st
        elif "did not participate" in prac or "out (definitely" in prac:
            out[str(r["full_name"]).lower()] = "doubtful"
    return out

"""Daily card builder: candidates -> verification -> three tiers -> stakes.

Pricing logic (identical for every tier):

  fair probability   From the books' consensus: each book's two-way no-vig
                     probability at its own line is converted into an implied
                     mean of our margin/total distribution (same key-number
                     model the backtest uses); the median across books is the
                     market-implied distribution. That gives a fair
                     probability at ANY line (alternate spreads included).
  final probability  logit(fair) + w * (logit(model) - logit(fair)), where w
                     is the out-of-sample model weight from the backtest
                     (currently 0 for every NFL market => final == fair).
  edge               final probability - break-even probability of the price
                     we would actually bet (best price across books).
  EV / $100          push-aware expected profit at that price.

So with w = 0, every recommended bet is a line-shopping edge: one book's
price is better than the market consensus by more than the vig. Nothing is
recommended because the model "likes" a side without proof.

Multi-leg bets: all legs at ONE book; joint probability from the correlated
simulation (same draws), never a product of independent probabilities for
same-game legs. The book's real same-game-parlay price is not published by
any free source, so each parlay shows the minimum SGP price worth taking.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import json
import pickle
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from bankroll.kelly import full_kelly_fraction
from data_pipeline.config import load_config
from edge.devig import american_to_decimal, american_to_implied_prob, decimal_to_american
from edgecard import freshness, store
from edgecard.pricing import breakeven_price, ev_per_100, novig_two_way
from models.distributions import (MARGIN_SUPPORT, TOTAL_SUPPORT, DiscreteDist, KeyWeights, moneyline_prob,
                                  spread_prob, total_prob)

ET = ZoneInfo("America/New_York")
EXCLUDED_FAIR_BOOKS = {"market_open", "consensus"}
TIERS = {
    "SAFE": dict(p_min=0.55, p_max=1.0, max_legs=2, min_edge=0.02),
    "MODERATE": dict(p_min=0.20, p_max=0.45, max_legs=4, min_edge=0.02),
    "LONG SHOT": dict(p_min=0.03, p_max=0.15, max_legs=4, min_edge=0.01),
}
MIN_EV_PER_100 = 1.0


def _logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _sigmoid(z):
    return 1 / (1 + np.exp(-z))


# --------------------------------------------------------------------------- #
# market-implied distributions
# --------------------------------------------------------------------------- #

@dataclass
class LeagueParams:
    league: str
    sigma_margin: float
    sigma_total: float
    kw_margin: KeyWeights
    kw_total: KeyWeights
    rho_fav: float
    weights: dict[str, float]           # model weight per market ('ml_home','spread_home','over')
    model: object | None = None          # GameModel or None
    groups: list[str] = field(default_factory=list)
    trained_through: str | None = None


def load_params(league: str) -> LeagueParams:
    p = store.data_dir() / "models" / f"{league.lower()}_game.pkl"
    if p.exists():
        art = pickle.load(open(p, "rb"))
        gm, cal = art["model"], art["calibrators"]
        ref_total = 44.0 if league == "NFL" else 225.0
        return LeagueParams(league, float(gm.sigma_margin(ref_total)), float(gm.sigma_total(ref_total)), gm.kw_margin,
                            gm.kw_total, gm.joint.rho_fav, {m: cal.w(m) for m in ("ml_home", "spread_home", "over")},
                            gm, art.get("groups", []), art.get("trained_through"))
    # no model yet (e.g. NBA before its backtest has run): market-only
    if league == "NFL":
        return LeagueParams(league, 13.3, 13.5, KeyWeights.flat(MARGIN_SUPPORT), KeyWeights.flat(TOTAL_SUPPORT), 0.0,
                            {"ml_home": 0.0, "spread_home": 0.0, "over": 0.0})
    return LeagueParams(league, 12.5, 18.5, KeyWeights.flat(MARGIN_SUPPORT), KeyWeights.flat(TOTAL_SUPPORT), 0.0,
                        {"ml_home": 0.0, "spread_home": 0.0, "over": 0.0})


def _solve_mu(target_prob: float, prob_fn, lo: float, hi: float) -> float:
    """Bisection for the mean at which prob_fn(mu) == target (prob_fn increasing)."""
    for _ in range(40):
        mid = (lo + hi) / 2
        if prob_fn(mid) < target_prob:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def implied_margin_mu(p_home_cover: float, home_point: float, lp: LeagueParams) -> float:
    return _solve_mu(p_home_cover, lambda mu: spread_prob(DiscreteDist.build(mu, lp.sigma_margin, lp.kw_margin), home_point,
                                                          "home").cover_given_no_push, -40, 40)


def implied_margin_mu_ml(p_home: float, lp: LeagueParams) -> float:
    return _solve_mu(p_home, lambda mu: moneyline_prob(DiscreteDist.build(mu, lp.sigma_margin, lp.kw_margin),
                                                       "home").cover_given_no_push, -40, 40)


def implied_total_mu(p_over: float, line: float, lp: LeagueParams) -> float:
    return _solve_mu(p_over, lambda mu: total_prob(DiscreteDist.build(mu, lp.sigma_total, lp.kw_total), line,
                                                   "over").cover_given_no_push, line - 60, line + 60)


def consensus(lines: pd.DataFrame, lp: LeagueParams, line_type: str = "current") -> dict[str, float]:
    """Median implied means across books for one game: mu_spread, mu_ml, mu_total."""
    out: dict[str, list[float]] = {"mu_spread": [], "mu_ml": [], "mu_total": []}
    if line_type == "open":
        cur = lines[lines["line_type"] == "open"]          # ESPN per-book opens + Action Network's opening line
    else:
        cur = lines[(lines["line_type"] == "current") & ~lines["book"].isin(EXCLUDED_FAIR_BOOKS)]
    for (book, market), d in cur.groupby(["book", "market"]):
        sides = {r["side"]: r for _, r in d.iterrows()}
        try:
            if market == "spread" and {"home", "away"} <= sides.keys():
                ph, _ = novig_two_way(sides["home"]["price"], sides["away"]["price"])
                out["mu_spread"].append(implied_margin_mu(ph, float(sides["home"]["point"]), lp))
            elif market == "moneyline" and {"home", "away"} <= sides.keys():
                ph, _ = novig_two_way(sides["home"]["price"], sides["away"]["price"])
                out["mu_ml"].append(implied_margin_mu_ml(ph, lp))
            elif market == "total" and {"over", "under"} <= sides.keys():
                po, _ = novig_two_way(sides["over"]["price"], sides["under"]["price"])
                out["mu_total"].append(implied_total_mu(po, float(sides["over"]["point"]), lp))
        except (TypeError, ValueError):
            continue
    res = {k: float(np.median(v)) for k, v in out.items() if v}
    res.update({f"n_{k}": len(v) for k, v in out.items()})
    return res


# --------------------------------------------------------------------------- #
# candidates
# --------------------------------------------------------------------------- #

@dataclass
class Leg:
    league: str
    game_key: str
    matchup: str
    kickoff: str
    kind: str                 # spread | moneyline | total | prop
    side: str                 # home | away | over | under
    point: float | None
    book: str
    price: float
    p_fair: float
    p_model: float | None
    p_final: float
    p_push: float
    label: str
    player: str | None = None
    market: str | None = None
    reasons: list[str] = field(default_factory=list)
    price_source: str = "posted"

    @property
    def edge(self) -> float:
        return self.p_final - american_to_implied_prob(self.price) * (1 - self.p_push)

    @property
    def ev100(self) -> float:
        return ev_per_100(self.p_final, self.price, self.p_push)

    def sim_spec(self) -> dict:
        return {"kind": self.kind, "side": self.side, "point": self.point, "player": self.player, "market": self.market}


def _game_dists(mu_m: float, mu_t: float, lp: LeagueParams):
    return DiscreteDist.build(mu_m, lp.sigma_margin, lp.kw_margin), DiscreteDist.build(mu_t, lp.sigma_total, lp.kw_total)


def game_candidates(ev: pd.Series, lines: pd.DataFrame, lp: LeagueParams, model_mu: tuple[float, float] | None,
                    cons: dict, cons_open: dict) -> list[Leg]:
    legs: list[Leg] = []
    matchup = f"{ev['away_team']} @ {ev['home_team']}"
    cur = lines[(lines["line_type"] == "current") & ~lines["book"].isin(EXCLUDED_FAIR_BOOKS)]
    mdl_m = mdl_t = None
    if model_mu is not None:
        mdl_m, mdl_t = _game_dists(*model_mu, lp)

    for _, r in cur.iterrows():
        kind, side, point, price = r["market"], r["side"], r["point"], float(r["price"])
        if kind in ("spread", "moneyline"):
            mu_key = "mu_spread" if kind == "spread" else "mu_ml"
            if mu_key not in cons:
                continue
            fair_m, _ = _game_dists(cons[mu_key], cons.get("mu_total", 44.0), lp)
            if kind == "spread":
                bp = spread_prob(fair_m, float(point), side)
                bm = spread_prob(mdl_m, float(point), side) if mdl_m else None
                w = lp.weights.get("spread_home", 0.0)
                label = f"{ev['home_team'] if side == 'home' else ev['away_team']} {float(point):+g}"
            else:
                bp = moneyline_prob(fair_m, side)
                bm = moneyline_prob(mdl_m, side) if mdl_m else None
                w = lp.weights.get("ml_home", 0.0)
                label = f"{ev['home_team'] if side == 'home' else ev['away_team']} ML"
        elif kind == "total":
            if "mu_total" not in cons:
                continue
            _, fair_t = _game_dists(cons.get("mu_spread", 0.0), cons["mu_total"], lp)
            bp = total_prob(fair_t, float(point), side)
            bm = total_prob(mdl_t, float(point), side) if mdl_t else None
            w = lp.weights.get("over", 0.0)
            label = f"{side.title()} {float(point):g} ({matchup})"
        else:
            continue
        # anchored final probability (win prob unconditional on push)
        p_fair_c = bp.cover_given_no_push
        p_model_c = bm.cover_given_no_push if bm else None
        p_final_c = p_fair_c if (p_model_c is None or w == 0) else float(_sigmoid(_logit(p_fair_c) + w * (_logit(p_model_c) - _logit(p_fair_c))))
        p_final = p_final_c * (1 - bp.push)
        leg = Leg(league=ev["league"], game_key=ev["game_key"], matchup=matchup, kickoff=ev["commence_time"], kind=kind,
                  side=side, point=None if pd.isna(point) else float(point), book=r["book"], price=price,
                  p_fair=bp.win, p_model=None if bm is None else bm.win, p_final=p_final, p_push=bp.push, label=label)
        legs.append(leg)
    return legs


def best_price_legs(legs: list[Leg]) -> list[Leg]:
    """For each (game, kind, side, point) keep the best price across books."""
    best: dict[tuple, Leg] = {}
    for L in legs:
        k = (L.game_key, L.kind, L.side, L.point, L.player, L.market)
        if k not in best or american_to_decimal(L.price) > american_to_decimal(best[k].price):
            best[k] = L
    return list(best.values())


# --------------------------------------------------------------------------- #
# tiers
# --------------------------------------------------------------------------- #

@dataclass
class Bet:
    tier: str
    legs: list[Leg]
    book: str
    price: float                # American price of the whole bet (parlay: product of leg prices)
    p_joint: float
    p_push: float
    correlated: bool
    ev100: float
    edge: float
    min_price: float
    status: str = "OK"
    recheck_at: str | None = None
    flags: list[dict] = field(default_factory=list)
    stake: float = 0.0
    kelly_fraction: float = 0.0
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        raw = "|".join(f"{L.game_key}:{L.kind}:{L.side}:{L.point}:{L.player}:{L.book}" for L in self.legs) + self.tier
        return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _parlay(legs: list[Leg], sims: dict, tier: str) -> Bet | None:
    from edgecard.odds import EXCHANGES

    if len({L.book for L in legs}) != 1 or legs[0].book in EXCHANGES:
        return None  # parlays exist only at one sportsbook; exchanges don't sell them
    if len({(L.game_key, L.kind, L.player, L.market) for L in legs}) != len(legs):
        return None  # two sides / lines of the same market
    by_game: dict[str, list[Leg]] = {}
    for L in legs:
        by_game.setdefault(L.game_key, []).append(L)
    p = 1.0
    correlated = False
    for gk, gl in by_game.items():
        if len(gl) == 1:
            p *= gl[0].p_final
        else:
            sim = sims.get(gk)
            if sim is None:
                return None  # no correlated joint available -> don't guess
            correlated = True
            p *= sim.prob([L.sim_spec() for L in gl])
    dec = 1.0
    for L in legs:
        dec *= american_to_decimal(L.price)
    price = float(decimal_to_american(dec))
    ev = p * (dec - 1) * 100 - (1 - p) * 100
    return Bet(tier=tier, legs=list(legs), book=legs[0].book, price=price, p_joint=p, p_push=0.0, correlated=correlated,
               ev100=ev, edge=p - 1 / dec, min_price=breakeven_price(p, min_edge=0.02))


def choose_tier(tier: str, singles: list[Leg], sims: dict, exclude_ids: set[str]) -> list[Bet]:
    """All +EV bets in the tier's probability band, best EV first."""
    t = TIERS[tier]
    out: list[Bet] = []
    for L in singles:
        if t["p_min"] <= L.p_final <= t["p_max"] and L.edge >= t["min_edge"] and L.ev100 >= MIN_EV_PER_100:
            b = Bet(tier=tier, legs=[L], book=L.book, price=L.price, p_joint=L.p_final, p_push=L.p_push, correlated=False,
                    ev100=L.ev100, edge=L.edge, min_price=breakeven_price(L.p_final, 0.02, L.p_push))
            out.append(b)
    # multi-leg: only from individually non-negative legs (a -EV leg can't help an honest parlay
    # unless correlation is doing the work, which is only possible within one game)
    pool = [L for L in singles if L.ev100 > -2.0][:40]
    for n in range(2, t["max_legs"] + 1):
        for combo in itertools.combinations(pool, n):
            b = _parlay(list(combo), sims, tier)
            if b and t["p_min"] <= b.p_joint <= t["p_max"] and b.edge >= t["min_edge"] and b.ev100 >= MIN_EV_PER_100:
                out.append(b)
    out = [b for b in out if b.id not in exclude_ids]
    out.sort(key=lambda b: (-b.ev100, len(b.legs)))
    return out


# --------------------------------------------------------------------------- #
# staking
# --------------------------------------------------------------------------- #

def stake_bets(bets: list[Bet], bankroll: float, cfg: dict) -> None:
    kf = cfg["kelly"]["kelly_fraction"]
    cap_bet = cfg["kelly"]["max_bet_pct_of_bankroll"]
    cap_day = cfg["kelly"].get("max_day_pct_of_bankroll", 0.05)
    for b in bets:
        if b.status == "VETO":
            b.stake = 0.0
            continue
        f = full_kelly_fraction(b.p_joint, b.price) * kf
        b.kelly_fraction = f
        b.stake = round(min(f, cap_bet) * bankroll, 2)
    total = sum(b.stake for b in bets)
    if total > cap_day * bankroll > 0:
        scale = cap_day * bankroll / total
        for b in bets:
            b.stake = round(b.stake * scale, 2)
            b.notes.append(f"stake scaled x{scale:.2f} to respect the {cap_day:.0%} daily cap")


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #

def _load_events(league: str) -> pd.DataFrame:
    ev = store.read_parquet_glob(("events", league.lower()), since=dt.date.today() - dt.timedelta(days=2))
    if ev.empty:
        return ev
    ev = ev.sort_values("captured_at").groupby("game_key").tail(1)
    now = pd.Timestamp.now(tz="UTC")
    ct = pd.to_datetime(ev["commence_time"], utc=True)
    horizon = pd.Timedelta(days=7) if league == "NFL" else pd.Timedelta(hours=30)
    return ev[(ct > now) & (ct <= now + horizon) & (ev["status"] == "pre")].reset_index(drop=True)


def build_league_card(league: str, bankroll: float, mode: str, cfg: dict) -> dict:
    from edgecard.odds import latest_lines, latest_props
    from news.verify import fetch_injury_designations, line_move_flag, scan_news, verdict_for_bet

    lp = load_params(league)
    events = _load_events(league)
    card = {"league": league, "n_games": int(len(events)), "tiers": {}, "model": {
        "weights": lp.weights, "feature_groups": lp.groups, "trained_through": lp.trained_through,
        "note": ("model weight is 0 in every market: bets below come only from price differences between books "
                 "(line shopping), never from the model's opinion") if not any(lp.weights.values()) else
                "model weight > 0 in some markets (earned out of sample)"}}
    if events.empty:
        for t in TIERS:
            card["tiers"][t] = {"bet": None, "message": f"NO {'LONG SHOT TODAY' if t == 'LONG SHOT' else 'BET'}",
                                "reason": f"no {league} games in the card window"}
        return card
    lines = latest_lines(league)
    model_mu = _model_means(league, events, lp)
    # official injury designations first: they feed the player projections
    from news.verify import usage_status

    flags = fetch_injury_designations(league)
    flagged_players = {f.player for f in flags if f.player}
    _PW_CACHE["statuses"] = {p.lower(): st for p in flagged_players if (st := usage_status(flags, p))}
    sims: dict = {}
    singles: list[Leg] = []
    game_info: dict = {}
    for _, ev in events.iterrows():
        ev = ev.copy()
        ev["league"] = league
        gl = lines[lines["game_key"] == ev["game_key"]] if not lines.empty else pd.DataFrame()
        if gl.empty:
            continue
        cons = consensus(gl, lp)
        cons_open = consensus(gl, lp, line_type="open")
        mm = model_mu.get(ev["game_key"])
        legs = game_candidates(ev, gl, lp, mm, cons, cons_open)
        singles += legs
        game_info[ev["game_key"]] = {"cons": cons, "cons_open": cons_open, "model_mu": mm, "event": ev}
        if "mu_spread" in cons and "mu_total" in cons:
            sims[ev["game_key"]] = _market_sim(league, ev, cons, lp)
    singles = best_price_legs(singles)
    for L in singles:
        L.reasons = _reasons(L, lines, game_info.get(L.game_key, {}), lp)

    # verification: 48h news scan on the players who matter
    teams = sorted(set(events["home_team"]) | set(events["away_team"]))
    key_players = _key_players(league, teams)
    # ESPN's per-team stat leaders are always key players (both leagues)
    for js in events.get("leaders", pd.Series(dtype=str)).dropna():
        for nm, tm in json.loads(js):
            if (nm, tm) not in key_players:
                key_players.append((nm, tm))
    flags += scan_news(league, key_players, teams if mode == "full" else [], hours=48)
    freshness.flush()

    used: set[str] = set()
    for tier in TIERS:
        cands = choose_tier(tier, singles, sims, used)
        chosen = None
        for b in cands[:25]:
            gteams = {game_info[L.game_key]["event"]["home_team"] for L in b.legs} | \
                     {game_info[L.game_key]["event"]["away_team"] for L in b.legs}
            kps = [p for p, t in key_players if t in gteams]
            kickoff = min(pd.Timestamp(L.kickoff) for L in b.legs).to_pydatetime()
            status, recheck, rel = verdict_for_bet(flags, kps, list(gteams), kickoff,
                                                   recheck_lead_minutes=90 if league == "NFL" else 30)
            for L in b.legs:
                gi = game_info[L.game_key]
                mv = _line_move(L, gi, lp)
                if mv:
                    rel.append(mv.as_dict())
                    if mv.severity >= 2 and status == "OK":
                        status = "WAIT"
                        recheck = recheck or (kickoff - dt.timedelta(minutes=60)).isoformat()
            b.status, b.recheck_at, b.flags = status, recheck, rel[:12]
            if status == "VETO":
                continue
            chosen = b
            break
        if chosen is None:
            card["tiers"][tier] = {"bet": None, "message": "NO LONG SHOT TODAY" if tier == "LONG SHOT" else "NO BET",
                                   "reason": _no_bet_reason(tier, singles, lp),
                                   "best_candidates_considered": len(cands)}
            continue
        used.add(chosen.id)
        card["tiers"][tier] = {"bet": chosen}
    bets = [v["bet"] for v in card["tiers"].values() if v.get("bet") is not None]
    stake_bets(bets, bankroll, cfg)
    for t, v in card["tiers"].items():
        if v.get("bet") is not None:
            card["tiers"][t] = _bet_json(v["bet"])
    card["shadow_props"] = _shadow_props(league, events, latest_props(league), sims, key_players)
    card["flags_checked"] = len(flags)
    return card


def _model_means(league: str, events: pd.DataFrame, lp: LeagueParams) -> dict[str, tuple[float, float]]:
    """Model mean margin/total for upcoming games (even when its weight is 0 it
    is shown for context)."""
    if lp.model is None:
        return {}
    try:
        if league == "NFL":
            from edgecard.backtest import load_nfl_frame
            from edgecard.weather import apply_forecast_weather

            frame = load_nfl_frame()
            frame = apply_forecast_weather(frame, events)
            fut = frame[~frame["is_final"]]
            preds = lp.model.predict_frame(fut)
            key = {}
            for _, r in fut.iterrows():
                d = pd.Timestamp(r["kickoff"]).strftime("%Y%m%d")
                key[f"NFL_{d}_{r['away_team']}_{r['home_team']}"] = r["game_id"]
            pm = preds.set_index("game_id")
            out = {}
            for gk in events["game_key"]:
                gid = key.get(gk)
                if gid is None:  # ET date vs local date can differ by a day for late games
                    alt = [k for k in key if k.split("_", 2)[2] == gk.split("_", 2)[2]]
                    gid = key.get(alt[0]) if alt else None
                if gid in pm.index:
                    out[gk] = (float(pm.loc[gid, "pred_margin"]), float(pm.loc[gid, "pred_total"]))
            return out
        from edgecard.nba import nba_model_means

        return nba_model_means(events, lp)
    except Exception as exc:  # noqa: BLE001 — the card must still build market-only
        print(f"  model means unavailable ({type(exc).__name__}: {exc}); card is market-only")
        return {}


def _market_sim(league: str, ev: pd.Series, cons: dict, lp: LeagueParams):
    """Correlated sim at the MARKET-implied means (fair prices), with player
    projections for NFL so same-game props can be priced jointly."""
    from models.nfl_props import TeamProjection

    md = DiscreteDist.build(cons["mu_spread"], lp.sigma_margin, lp.kw_margin)
    if league == "NFL":
        from sim.nfl_sim import simulate_game

        H, A = _nfl_team_projections(ev)
        return simulate_game(md, cons["mu_total"], lp.sigma_total, lp.rho_fav, H, A, n=10000,
                             seed=int(hashlib.md5(ev["game_key"].encode()).hexdigest()[:6], 16))
    from sim.nba_sim import simulate_nba_game

    return simulate_nba_game(md, cons["mu_total"], lp.sigma_total, lp.rho_fav, ev, n=10000)


_PW_CACHE: dict = {}


def _nfl_team_projections(ev: pd.Series):
    from data_pipeline.sources.nflverse_hist import load
    from models.nfl_props import TeamProjection, project_team, team_volume_params, team_week_totals

    if "pw" not in _PW_CACHE:
        pw = load("nfl_player_weeks")
        pw = pw[pw["season_type"] == "REG"] if "season_type" in pw else pw
        _PW_CACHE["pw"] = pw.merge(team_week_totals(pw), on=["team", "season", "week"])
        _PW_CACHE["tg"] = load("nfl_team_games")
    pw, tg = _PW_CACHE["pw"], _PW_CACHE["tg"]
    s = int(pw["season"].max())
    w = int(pw.loc[pw["season"] == s, "week"].max()) + 1
    statuses = _PW_CACHE.get("statuses", {})
    out = []
    for team in (ev["home_team"], ev["away_team"]):
        try:
            out.append(project_team(pw, team, (s, w), *team_volume_params(tg, team, s, w), statuses=statuses))
        except Exception:  # noqa: BLE001
            out.append(TeamProjection(team=team, plays=62.0, pass_rate=0.58, rush_td_frac=0.4))
    return out[0], out[1]


def _key_players(league: str, teams: list[str]) -> list[tuple[str, str]]:
    """The players whose status can move a line: NFL QBs + top-usage skill
    players from the latest projections; NBA top-minutes players."""
    out: list[tuple[str, str]] = []
    if league == "NFL":
        try:
            for t in teams:
                H, _ = _nfl_team_projections(pd.Series({"home_team": t, "away_team": t}))
                ranked = sorted(H.players, key=lambda p: -(p.target_share + p.carry_share))[:3]
                if H.passer:
                    out.append((H.passer.player, t))
                out += [(p.player, t) for p in ranked if not H.passer or p.player != H.passer.player]
        except Exception:  # noqa: BLE001
            pass
    else:
        from edgecard.nba import nba_key_players

        out = nba_key_players(teams)
    return out


def _line_move(L: Leg, gi: dict, lp: LeagueParams):
    from news.verify import line_move_flag

    co, cn = gi.get("cons_open", {}), gi.get("cons", {})
    if L.kind == "spread" and "mu_spread" in co and "mu_spread" in cn:
        po = spread_prob(DiscreteDist.build(co["mu_spread"], lp.sigma_margin, lp.kw_margin), L.point, L.side).cover_given_no_push
        pn = spread_prob(DiscreteDist.build(cn["mu_spread"], lp.sigma_margin, lp.kw_margin), L.point, L.side).cover_given_no_push
    elif L.kind == "moneyline" and "mu_ml" in co and "mu_ml" in cn:
        po = moneyline_prob(DiscreteDist.build(co["mu_ml"], lp.sigma_margin, lp.kw_margin), L.side).cover_given_no_push
        pn = moneyline_prob(DiscreteDist.build(cn["mu_ml"], lp.sigma_margin, lp.kw_margin), L.side).cover_given_no_push
    elif L.kind == "total" and "mu_total" in co and "mu_total" in cn:
        po = total_prob(DiscreteDist.build(co["mu_total"], lp.sigma_total, lp.kw_total), L.point, L.side).cover_given_no_push
        pn = total_prob(DiscreteDist.build(cn["mu_total"], lp.sigma_total, lp.kw_total), L.point, L.side).cover_given_no_push
    else:
        return None
    return line_move_flag(po, pn, L.label)


def _reasons(L: Leg, lines: pd.DataFrame, gi: dict, lp: LeagueParams) -> list[str]:
    r = []
    fair_price = decimal_to_american(1 / max(L.p_final / (1 - L.p_push) if L.p_push < 1 else L.p_final, 1e-6))
    r.append(f"Best price {L.price:+.0f} at {L.book} vs market-consensus fair {fair_price:+.0f} "
             f"(fair win prob {L.p_final:.1%}; break-even at this price {american_to_implied_prob(L.price) * (1 - L.p_push):.1%}).")
    gl = lines[(lines["game_key"] == L.game_key) & (lines["market"] == L.kind) & (lines["side"] == L.side)
               & (lines["line_type"] == "current") & ~lines["book"].isin(EXCLUDED_FAIR_BOOKS)] if not lines.empty else pd.DataFrame()
    if len(gl):
        prices = ", ".join(f"{b} {p:+.0f}{'' if pd.isna(pt) else f' ({pt:+g})'}" for b, p, pt in
                           gl[["book", "price", "point"]].itertuples(index=False))
        r.append(f"Prices seen for this side: {prices}.")
    mm = gi.get("model_mu")
    if mm is not None and L.p_model is not None:
        w = lp.weights.get({"spread": "spread_home", "moneyline": "ml_home", "total": "over"}.get(L.kind, ""), 0.0)
        r.append(f"Model: margin {mm[0]:+.1f}, total {mm[1]:.1f} -> {L.p_model:.1%} for this side; weight used {w:.2f} "
                 f"({'not trusted: no out-of-sample edge vs closing line' if w == 0 else 'earned out of sample'}).")
    return r[:3]


def _no_bet_reason(tier: str, singles: list[Leg], lp: LeagueParams) -> str:
    t = TIERS[tier]
    band = [L for L in singles if t["p_min"] <= L.p_final <= t["p_max"]]
    if not singles:
        return "no priced markets available yet"
    best = max((L.edge for L in band), default=None)
    if best is None:
        return f"no single bet or same-book combination lands in the {t['p_min']:.0%}-{t['p_max']:.0%} win-probability band with positive EV"
    return (f"best candidate in the {t['p_min']:.0%}-{t['p_max']:.0%} band has edge {best:+.1%} over its break-even — "
            f"below the {t['min_edge']:.0%} threshold; nothing is forced")


def _bet_json(b: Bet) -> dict:
    return {
        "id": b.id, "tier": b.tier, "status": b.status, "recheck_at": b.recheck_at,
        "description": " + ".join(L.label for L in b.legs), "book": b.book, "price": round(b.price),
        "legs": [{"label": L.label, "game": L.matchup, "kickoff": L.kickoff, "market": L.kind, "side": L.side,
                  "point": L.point, "player": L.player, "book": L.book, "price": L.price, "price_source": L.price_source,
                  "p_final": round(L.p_final, 4), "p_fair": round(L.p_fair, 4),
                  "p_model": None if L.p_model is None else round(L.p_model, 4), "p_push": round(L.p_push, 4),
                  "novig_implied": round(L.p_fair / max(1 - L.p_push, 1e-9), 4), "game_key": L.game_key} for L in b.legs],
        "model_prob": round(b.p_joint, 4),
        "novig_market_prob": round(float(np.prod([L.p_fair for L in b.legs])) if not b.correlated else b.p_joint, 4),
        "price_implied_prob": round(1 / american_to_decimal(b.price), 4),
        "edge": round(b.edge, 4), "ev_per_100": round(b.ev100, 2), "stake": b.stake,
        "kelly_fraction_used": round(b.kelly_fraction, 4), "correlated_joint": b.correlated,
        "min_acceptable_price": round(b.min_price), "reasons": (b.legs[0].reasons if len(b.legs) == 1 else
                                                                [f"{L.label}: {L.reasons[0] if L.reasons else ''}" for L in b.legs][:3]),
        "flags": b.flags, "notes": b.notes + ([
            "Same-game joint probability comes from the correlated simulation; books adjust SGP prices for correlation "
            f"and free sources don't publish them — bet only if the book's SGP price is {round(b.min_price):+d} or better."]
            if b.correlated else []),
    }


def _shadow_props(league: str, events: pd.DataFrame, props: pd.DataFrame, sims: dict, key_players) -> dict:
    """Props are tracked in PAPER/SHADOW mode only: free sources give the
    line but not the price, and the props model has not yet shown skill
    against real prop markets. Listed so they can be tracked, not bet."""
    if props is None or props.empty:
        return {"status": "no prop lines available", "rows": []}
    rows = []
    for _, p in props.iterrows():
        sim = sims.get(p["game_key"])
        if sim is None or p["market"] is None:
            continue
        spec = {"kind": "prop", "player": p["player"], "market": p["market"], "point": p["line"], "side": "over"}
        if (p["player"], p["market"]) not in sim.stats:
            continue
        po = sim.prob([spec])
        rows.append({"player": p["player"], "team": p["team"], "market": p["market"], "line": p["line"],
                     "p_over_sim": round(po, 3), "sim_median": float(np.median(sim.stats[(p["player"], p["market"])])),
                     "game_key": p["game_key"], "book": p["book"], "price": "not published (assumed -110)"})
    rows.sort(key=lambda r: -abs(r["p_over_sim"] - 0.5))
    return {"status": "SHADOW ONLY — tracked for calibration, not recommended (no free prop prices; model unproven vs prop markets)",
            "rows": rows[:25]}


def build_and_publish(leagues: list[str], mode: str = "full", bankroll: float | None = None) -> int:
    cfg = load_config()
    bankroll = bankroll or float(store.read_json("ledger", "bankroll.json", default={}).get("bankroll", cfg["bankroll"]["starting_bankroll"]))
    now = dt.datetime.now(dt.timezone.utc)
    card = {"generated_at": now.isoformat(timespec="seconds"), "generated_at_et": now.astimezone(ET).strftime("%a %b %d %I:%M %p ET"),
            "mode": mode, "paper_mode": bool(cfg.get("edgecard", {}).get("paper_mode", True)), "bankroll": bankroll,
            "leagues": {}, "disclaimer": "Probabilities, not guarantees. Paper mode: nothing here is a real wager.",
            "backtest": _backtest_summaries()}
    for lg in leagues:
        try:
            card["leagues"][lg] = build_league_card(lg, bankroll, mode, cfg)
        except Exception as exc:  # noqa: BLE001 — one league failing must not kill the other
            import traceback

            traceback.print_exc()
            card["leagues"][lg] = {"league": lg, "error": f"{type(exc).__name__}: {exc}", "tiers": {
                t: {"bet": None, "message": "NO BET", "reason": "card build failed; see logs"} for t in TIERS}}
    card["freshness"] = freshness.flush()
    from edgecard.tracking import clv_warning, log_recommendations

    card["warnings"] = [w for w in [clv_warning()] if w]
    day = now.astimezone(ET).date().isoformat()
    store.write_json(card, "cards", day, f"{mode}.json")
    store.write_json(card, "cards", "latest.json")
    log_recommendations(card)
    print(render_text(card))
    return 0


def _backtest_summaries() -> dict:
    out = {}
    for lg in ("nfl", "nba"):
        r = store.read_json("reports", f"backtest_{lg}.json")
        if r:
            out[lg.upper()] = {"verdicts": r.get("verdicts", []), "test_seasons": r.get("test_seasons"),
                               "kept_groups": r.get("ablation", {}).get("kept", []),
                               "dropped_groups": r.get("ablation", {}).get("dropped", []),
                               "generated_at": r.get("generated_at")}
    return out


def render_text(card: dict) -> str:
    lines = [f"EDGE CARD — {card['generated_at_et']}  [{card['mode']}]  {'PAPER MODE' if card['paper_mode'] else 'LIVE'}",
             card["disclaimer"], ""]
    for lg, c in card["leagues"].items():
        lines.append(f"== {lg} ({c.get('n_games', 0)} games in window) ==")
        if c.get("model", {}).get("note"):
            lines.append(f"   model: {c['model']['note']}")
        for t in TIERS:
            v = c["tiers"].get(t, {})
            if not v or v.get("bet", "x") is None:
                lines.append(f"  {t:<10} {v.get('message', 'NO BET')} — {v.get('reason', '')}")
                continue
            lines.append(f"  {t:<10} [{v['status']}] {v['description']}  @ {v['book']} {v['price']:+d}")
            lines.append(f"             model {v['model_prob']:.1%} | no-vig {v['novig_market_prob']:.1%} | price-implied "
                         f"{v['price_implied_prob']:.1%} | edge {v['edge']:+.1%} | EV ${v['ev_per_100']:+.2f}/100 | "
                         f"stake ${v['stake']:.2f} | min price {v['min_acceptable_price']:+d}")
            for r in v["reasons"]:
                lines.append(f"             - {r}")
            if v.get("recheck_at"):
                lines.append(f"             WAIT — recheck after {pd.Timestamp(v['recheck_at']).tz_convert(ET).strftime('%a %I:%M %p ET')}")
            for f in v.get("flags", [])[:4]:
                lines.append(f"             flag: [{f['flag_type']}/{f['severity']}] {f.get('player') or ''} {f['text'][:90]} "
                             f"({f['source']}, {str(f['timestamp'])[:16]})")
        lines.append("")
    for w in card.get("warnings", []):
        lines.append(f"WARNING: {w}")
    return "\n".join(lines)

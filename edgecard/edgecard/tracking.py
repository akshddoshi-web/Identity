"""Recommendation log, settlement, CLV / ROI / calibration reporting.

  log_recommendations(card)   every tier pick (OK or WAIT) is appended to
                              ledger/recommendations.csv the moment the card
                              is published — before the game — and never
                              edited. Shadow props go to ledger/shadow_props.csv.
  settle(league)              after kickoff: closing line (last snapshot
                              before kickoff), CLV at OUR line, result, paper
                              profit. Appends to ledger/settlements.csv.
  weekly_report()             CLV, ROI and calibration by tier and bet type,
                              last 7 days and all time.
  clv_warning()               loud warning once 200+ bets are settled and
                              average CLV is negative.

CLV definition: no-vig closing probability of our side AT OUR LINE (market-
implied distribution, so a -3 bet is judged against a -3.5 close correctly)
minus the break-even probability of the price we took. Positive = we beat
the close.
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd

from edge.devig import american_to_decimal, american_to_implied_prob
from edgecard import store

MIN_BETS_FOR_WARNING = 200


def log_recommendations(card: dict) -> int:
    rows, props = [], []
    now = card["generated_at"]
    for lg, c in card.get("leagues", {}).items():
        for tier, v in (c.get("tiers") or {}).items():
            if not v or v.get("id") is None:
                continue
            rows.append({
                "rec_id": f"{v['id']}_{card['mode']}_{now[:10]}", "bet_id": v["id"], "created_at": now, "mode": card["mode"],
                "paper": card["paper_mode"], "league": lg, "tier": tier, "status": v["status"],
                "description": v["description"], "book": v["book"], "price": v["price"], "model_prob": v["model_prob"],
                "novig_prob": v["novig_market_prob"], "edge": v["edge"], "ev_per_100": v["ev_per_100"], "stake": v["stake"],
                "n_legs": len(v["legs"]), "bet_type": v["legs"][0]["market"] if len(v["legs"]) == 1 else "parlay",
                "kickoff": min(L["kickoff"] for L in v["legs"]), "legs_json": json.dumps(v["legs"]),
            })
        for p in (c.get("shadow_props") or {}).get("rows", []):
            props.append(dict(p, created_at=now, league=lg))
    if rows:
        df = pd.DataFrame(rows)
        old = store.read_csv("ledger", "recommendations.csv")
        if not old.empty:
            df = df[~df["rec_id"].isin(set(old["rec_id"]))]
        if len(df):
            store.append_csv(df, "ledger", "recommendations.csv")
    if props:
        store.append_csv(pd.DataFrame(props), "ledger", "shadow_props.csv")
    return len(rows)


def _closing_rows(league: str, game_key: str, kickoff: pd.Timestamp) -> pd.DataFrame:
    hist = store.read_parquet_glob(("odds", league.lower()), since=(kickoff - pd.Timedelta(days=8)).date())
    if hist.empty:
        return hist
    h = hist[(hist["game_key"] == game_key) & (hist["line_type"] == "current")]
    h = h[pd.to_datetime(h["captured_at"], utc=True) < kickoff]
    return h.sort_values("captured_at").groupby(["book", "market", "side"]).tail(1)


def _leg_result(L: dict, home: float, away: float, stats: dict | None = None) -> str:
    m, t = home - away, home + away
    kind, side, pt = L["market"], L["side"], L.get("point")
    if kind == "moneyline":
        v = m if side == "home" else -m
    elif kind == "spread":
        v = (m if side == "home" else -m) + pt
    elif kind == "total":
        v = (t - pt) if side == "over" else (pt - t)
    else:
        return "unsettled"
    return "win" if v > 0 else "loss" if v < 0 else "push"


def _leg_clv(L: dict, close: pd.DataFrame, league: str) -> float | None:
    from edgecard.card import consensus, load_params
    from models.distributions import DiscreteDist, moneyline_prob, spread_prob, total_prob

    if close.empty:
        return None
    lp = load_params(league)
    cons = consensus(close.assign(line_type="current"), lp)
    try:
        if L["market"] == "spread" and "mu_spread" in cons:
            p = spread_prob(DiscreteDist.build(cons["mu_spread"], lp.sigma_margin, lp.kw_margin), L["point"], L["side"])
        elif L["market"] == "moneyline" and "mu_ml" in cons:
            p = moneyline_prob(DiscreteDist.build(cons["mu_ml"], lp.sigma_margin, lp.kw_margin), L["side"])
        elif L["market"] == "total" and "mu_total" in cons:
            p = total_prob(DiscreteDist.build(cons["mu_total"], lp.sigma_total, lp.kw_total), L["point"], L["side"])
        else:
            return None
    except (TypeError, ValueError):
        return None
    # push-aware: compare win prob against the break-even win prob at our price
    breakeven = american_to_implied_prob(L["price"]) * (1 - p.push)
    return float(p.win - breakeven)


def settle(league: str) -> int:
    from edgecard.odds import fetch_events

    recs = store.read_csv("ledger", "recommendations.csv")
    if recs.empty:
        print("nothing to settle")
        return 0
    done = store.read_csv("ledger", "settlements.csv")
    done_ids = set(done["rec_id"]) if not done.empty else set()
    todo = recs[(recs["league"] == league) & ~recs["rec_id"].isin(done_ids)]
    now = pd.Timestamp.now(tz="UTC")
    todo = todo[pd.to_datetime(todo["kickoff"], utc=True) < now - pd.Timedelta(hours=4)]
    if todo.empty:
        print(f"{league}: nothing to settle")
        return 0
    dates = sorted({pd.Timestamp(k).tz_convert("America/New_York").strftime("%Y%m%d") for k in
                    (L["kickoff"] for legs in todo["legs_json"] for L in json.loads(legs))})
    finals = {e.game_key: e for e in fetch_events(league, dates=dates) if e.status == "post"}
    out = []
    for _, r in todo.iterrows():
        legs = json.loads(r["legs_json"])
        results, clvs = [], []
        for L in legs:
            e = finals.get(L["game_key"])
            if e is None or e.home_score is None:
                results.append("unsettled")
                continue
            results.append(_leg_result(L, e.home_score, e.away_score))
            if len(legs) == 1:
                clvs.append(_leg_clv(L, _closing_rows(league, L["game_key"], pd.Timestamp(L["kickoff"])), league))
        if "unsettled" in results:
            continue
        if "loss" in results:
            outcome = "loss"
        elif all(x == "push" for x in results):
            outcome = "push"
        else:
            outcome = "win"
        dec = 1.0
        for L, res in zip(legs, results):
            if res != "push":
                dec *= american_to_decimal(L["price"])
        profit = (dec - 1) * r["stake"] if outcome == "win" else (-r["stake"] if outcome == "loss" else 0.0)
        out.append({"rec_id": r["rec_id"], "settled_at": now.isoformat(), "league": league, "tier": r["tier"],
                    "bet_type": r["bet_type"], "status_at_pub": r["status"], "outcome": outcome, "stake": r["stake"],
                    "profit": round(profit, 2), "model_prob": r["model_prob"], "won": float(outcome == "win"),
                    "clv": clvs[0] if clvs else np.nan})
    if out:
        store.append_csv(pd.DataFrame(out), "ledger", "settlements.csv")
        br = store.read_json("ledger", "bankroll.json", default=None)
        if br is None:
            from data_pipeline.config import load_config

            br = {"bankroll": float(load_config()["bankroll"]["starting_bankroll"]), "paper": True}
        br["bankroll"] = round(br["bankroll"] + sum(o["profit"] for o in out if o["status_at_pub"] == "OK"), 2)
        br["updated_at"] = now.isoformat()
        store.write_json(br, "ledger", "bankroll.json")
    print(f"{league}: settled {len(out)}")
    return len(out)


def _summ(d: pd.DataFrame) -> dict:
    if d.empty:
        return {"n": 0}
    staked = d["stake"].sum()
    res = {"n": int(len(d)), "wins": int((d["outcome"] == "win").sum()), "pushes": int((d["outcome"] == "push").sum()),
           "units_profit": round(float(d["profit"].sum()), 2), "staked": round(float(staked), 2),
           "roi": round(float(d["profit"].sum() / staked), 4) if staked > 0 else None,
           "mean_clv": round(float(d["clv"].mean()), 4) if d["clv"].notna().any() else None,
           "clv_n": int(d["clv"].notna().sum()),
           "brier": round(float(((d["model_prob"] - d["won"]) ** 2).mean()), 4),
           "avg_model_prob": round(float(d["model_prob"].mean()), 4), "hit_rate": round(float(d["won"].mean()), 4)}
    res["small_sample"] = res["n"] < MIN_BETS_FOR_WARNING
    return res


def weekly_report() -> dict:
    s = store.read_csv("ledger", "settlements.csv")
    rep: dict = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    if s.empty:
        rep["headline"] = "No settled recommendations yet (paper mode)."
        store.write_json(rep, "reports", "weekly.json")
        return rep
    s["settled_at"] = pd.to_datetime(s["settled_at"], utc=True)
    recent = s[s["settled_at"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)]
    for name, d in (("last_7_days", recent), ("all_time", s)):
        rep[name] = {"overall": _summ(d),
                     "by_tier": {t: _summ(x) for t, x in d.groupby("tier")},
                     "by_bet_type": {t: _summ(x) for t, x in d.groupby("bet_type")},
                     "by_league": {t: _summ(x) for t, x in d.groupby("league")}}
    if len(s) >= 20:
        q = pd.cut(s["model_prob"], [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 1.0])
        rep["calibration"] = s.groupby(q, observed=True).agg(pred=("model_prob", "mean"), actual=("won", "mean"),
                                                            n=("won", "size")).reset_index(drop=True).round(4).to_dict("records")
    a = rep["all_time"]["overall"]
    rep["headline"] = (f"All-time: {a['n']} settled, ROI {a['roi']:+.1%}, mean CLV "
                       f"{(a['mean_clv'] or 0):+.2%} (n={a['clv_n']})" + (" — small sample" if a["small_sample"] else ""))
    w = clv_warning()
    if w:
        rep["warning"] = w
    store.write_json(rep, "reports", "weekly.json")
    return rep


def clv_warning() -> str | None:
    s = store.read_csv("ledger", "settlements.csv")
    if s.empty or "clv" not in s:
        return None
    c = s["clv"].dropna()
    if len(c) >= MIN_BETS_FOR_WARNING and c.mean() < 0:
        return (f"Negative CLV over {len(c)} settled bets (mean {c.mean():+.2%}). The card is not beating the closing "
                f"line; treat its edges as unproven and stay in paper mode.")
    return None

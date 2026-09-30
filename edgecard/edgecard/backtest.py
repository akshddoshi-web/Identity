"""Walk-forward backtest + feature-group ablation + production model fit.

Protocol (NFL):
  for each test season T (first_test..latest):
      train mean/variance models on every final game in seasons < T
      predict every game in T (features are point-in-time, see nfl_features)
      calibrators for T are fitted ONLY on out-of-sample predictions from seasons < T
  metrics per market (home moneyline, home spread cover at the closing
  spread, over at the closing total), for:
      market     no-vig closing probability (the benchmark to beat)
      elo        Elo baseline (moneyline only)
      model      our distribution, isotonic-calibrated
      final      market-aware stacked probability (what the card uses)
  plus a flat-stake betting simulation at CLOSING prices when final - market
  >= threshold. Betting the close means CLV is zero by construction; the
  question the simulation answers is whether our probability beats the
  closing line at all. Live CLV is measured going forward (edgecard/tracking.py).

Ablation: each situational group is added to the base set on its own and
kept only if it lowers the model's mean out-of-sample log loss across the
three markets AND does so in at least half the test seasons. (The final,
market-anchored probability can't be the yardstick: when the model's weight
is 0 it equals the market no matter which features are used.)
"""
from __future__ import annotations

import datetime as dt
import json
import pickle

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from edgecard import store
from models.game_model import Calibrators, GameModel, MARKETS, model_market_probs

EDGE_THRESHOLD = 0.02
BASE_GROUPS = ["base"]
CANDIDATE_GROUPS = ["opp_adjusted", "pressure_redzone", "special_teams", "turnover_luck", "fatigue",
                    "cohesion", "motivation", "weather", "h2h", "altitude"]


def _ll(y, p):
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    ok = ~(np.isnan(y) | np.isnan(p))
    if ok.sum() < 20:
        return np.nan
    return float(log_loss(y[ok], p[ok], labels=[0, 1]))


def _brier(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    ok = ~(np.isnan(y) | np.isnan(p))
    return float(brier_score_loss(y[ok], p[ok])) if ok.sum() >= 20 else np.nan


def load_nfl_frame() -> pd.DataFrame:
    from data_pipeline.sources.nflverse_hist import load
    from models.nfl_features import build_nfl_features

    g = load("nfl_games")
    tg = load("nfl_team_games")
    try:
        tr = load("nfl_trades")
    except FileNotFoundError:
        tr = None
    try:
        pw = load("nfl_player_weeks")
    except FileNotFoundError:
        pw = None
    return build_nfl_features(g[g["season"] >= 2015], tg, tr, pw)


def walk_forward(frame: pd.DataFrame, feature_cols: list[str], first_test: int, last_test: int,
                 n_estimators: int | None = None) -> pd.DataFrame:
    """Returns OOS rows for every final game in [first_test, last_test],
    with model/market/elo/final probabilities and outcomes."""
    from models import game_model as gmod

    params_backup = dict(gmod.XGB_PARAMS)
    if n_estimators:
        gmod.XGB_PARAMS["n_estimators"] = n_estimators
    try:
        oos_all: list[pd.DataFrame] = []
        resid_pool: list[pd.DataFrame] = []
        for T in range(first_test - 2, last_test + 1):  # two warm-up folds feed variance/calibration
            train = frame[(frame["season"] < T) & frame["is_final"]]
            test = frame[(frame["season"] == T) & frame["is_final"]]
            if len(train) < 400 or test.empty:
                continue
            resid = pd.concat(resid_pool) if resid_pool else None
            gm = GameModel(feature_cols).fit(train, oos_resid=resid)
            preds = gm.predict_frame(test)
            mm = model_market_probs(gm, preds, test)
            mm["season"] = T
            mm = mm.merge(test[["game_id", "elo_prob", "week"]], on="game_id", how="left")
            resid_pool.append(pd.DataFrame({
                "resid_margin": mm["margin"] - mm["pred_margin"], "resid_total": mm["total_pts"] - mm["pred_total"],
                "pred_margin": mm["pred_margin"], "pred_total": mm["pred_total"],
                "margin": mm["margin"], "total_pts": mm["total_pts"]}))
            prior = pd.concat(oos_all) if oos_all else pd.DataFrame()
            cal = Calibrators.fit(prior) if len(prior) else Calibrators()
            for m in MARKETS:
                if f"model_{m}" not in mm:
                    continue
                mm[f"iso_{m}"] = cal.model_only(m, mm[f"model_{m}"].fillna(0.5).values)
                mm[f"final_{m}"] = cal.final(m, mm[f"model_{m}"].fillna(0.5).values, mm[f"mkt_{m}"].values)
            mm["calibrated_on_n"] = len(prior)
            oos_all.append(mm)
        out = pd.concat(oos_all, ignore_index=True)
        return out[out["season"] >= first_test].reset_index(drop=True)
    finally:
        gmod.XGB_PARAMS.clear()
        gmod.XGB_PARAMS.update(params_backup)


def _price_for(row: pd.Series, market: str, side_is_a: bool) -> float | None:
    cols = {"ml_home": ("home_moneyline", "away_moneyline"), "spread_home": ("home_spread_odds", "away_spread_odds"),
            "over": ("over_odds", "under_odds")}[market]
    v = row.get(cols[0] if side_is_a else cols[1])
    return float(v) if pd.notna(v) else None


def _payout(price: float) -> float:
    return price / 100 if price > 0 else 100 / -price


def betting_sim(oos: pd.DataFrame, frame: pd.DataFrame, threshold: float = EDGE_THRESHOLD) -> pd.DataFrame:
    f = frame.set_index("game_id")
    bets = []
    for _, r in oos.iterrows():
        g = f.loc[r["game_id"]]
        for m in MARKETS:
            pf, pm, y = r.get(f"final_{m}"), r.get(f"mkt_{m}"), r.get(f"y_{m}")
            if any(pd.isna(v) for v in (pf, pm)):
                continue
            for side_a, p_side, m_side in ((True, pf, pm), (False, 1 - pf, 1 - pm)):
                price = _price_for(g, m, side_a)
                if price is None or p_side - m_side < threshold:
                    continue
                ev = p_side * _payout(price) - (1 - p_side)
                if ev <= 0:
                    continue
                if pd.isna(y):
                    result = 0.0  # push
                else:
                    won = (y == 1.0) if side_a else (y == 0.0)
                    result = _payout(price) if won else -1.0
                bets.append({"game_id": r["game_id"], "season": r["season"], "market": m, "side_a": side_a,
                             "p": p_side, "p_mkt": m_side, "edge": p_side - m_side, "price": price, "ev": ev,
                             "profit": result})
    return pd.DataFrame(bets)


def summarize(oos: pd.DataFrame, frame: pd.DataFrame) -> dict:
    res: dict = {"markets": {}, "by_season": {}}
    for m in MARKETS:
        if f"y_{m}" not in oos or f"mkt_{m}" not in oos:
            res["markets"][m] = {"n": 0, "note": "no market lines available for this market in the test seasons"}
            continue
        d = oos.dropna(subset=[f"y_{m}", f"mkt_{m}"])
        row = {"n": int(len(d))}
        for k in ("mkt", "iso", "final", "model"):
            col = f"{k}_{m}"
            if col in d:
                row[f"logloss_{k}"] = _ll(d[f"y_{m}"], d[col])
                row[f"brier_{k}"] = _brier(d[f"y_{m}"], d[col])
        if m == "ml_home":
            row["logloss_elo"] = _ll(d["y_ml_home"], d["elo_prob"])
            row["brier_elo"] = _brier(d["y_ml_home"], d["elo_prob"])
        row["final_minus_market_logloss"] = row.get("logloss_final", np.nan) - row.get("logloss_mkt", np.nan)
        row["model_minus_market_logloss"] = row.get("logloss_iso", np.nan) - row.get("logloss_mkt", np.nan)
        # calibration table for the final probability
        if f"final_{m}" in d and len(d) > 50:
            q = pd.qcut(d[f"final_{m}"], 10, duplicates="drop")
            ct = d.groupby(q, observed=True).agg(pred=(f"final_{m}", "mean"), actual=(f"y_{m}", "mean"), n=(f"y_{m}", "size"))
            row["calibration_final"] = ct.reset_index(drop=True).round(4).to_dict("records")
            q2 = pd.qcut(d[f"iso_{m}"], 10, duplicates="drop")
            ct2 = d.groupby(q2, observed=True).agg(pred=(f"iso_{m}", "mean"), actual=(f"y_{m}", "mean"), n=(f"y_{m}", "size"))
            row["calibration_model"] = ct2.reset_index(drop=True).round(4).to_dict("records")
        res["markets"][m] = row
    for s, d in oos.groupby("season"):
        res["by_season"][int(s)] = {m: {"logloss_final": _ll(d[f"y_{m}"], d[f"final_{m}"]) if f"final_{m}" in d else None,
                                        "logloss_mkt": _ll(d[f"y_{m}"], d[f"mkt_{m}"])}
                                    for m in MARKETS if f"y_{m}" in d and f"mkt_{m}" in d}
    bets = betting_sim(oos, frame)
    if len(bets):
        b = {"n_bets": int(len(bets)), "roi": float(bets["profit"].sum() / len(bets)),
             "units": float(bets["profit"].sum()), "avg_edge": float(bets["edge"].mean()),
             "by_market": {m: {"n": int(len(x)), "roi": float(x["profit"].mean())} for m, x in bets.groupby("market")},
             "by_season": {int(s): {"n": int(len(x)), "roi": float(x["profit"].mean())} for s, x in bets.groupby("season")}}
        # bootstrap CI on ROI
        rng = np.random.default_rng(0)
        boots = [rng.choice(bets["profit"].values, len(bets)).mean() for _ in range(2000)]
        b["roi_ci95"] = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
    else:
        b = {"n_bets": 0}
    res["betting_at_close"] = b
    res["margin_rmse"] = float(np.sqrt(np.nanmean((oos["margin"] - oos["pred_margin"]) ** 2)))
    res["total_rmse"] = float(np.sqrt(np.nanmean((oos["total_pts"] - oos["pred_total"]) ** 2)))
    return res


def _mean_final_ll(oos: pd.DataFrame) -> tuple[float, dict[int, float]]:
    per_season = {}
    for s, d in oos.groupby("season"):
        vals = [_ll(d[f"y_{m}"], d[f"final_{m}"]) for m in MARKETS if f"final_{m}" in d and f"y_{m}" in d]
        per_season[int(s)] = float(np.nanmean(vals))
    vals = [_ll(oos[f"y_{m}"], oos[f"final_{m}"]) for m in MARKETS if f"final_{m}" in oos and f"y_{m}" in oos]
    return float(np.nanmean(vals)), per_season


def _mean_model_ll(oos: pd.DataFrame) -> tuple[float, dict[int, float]]:
    ok = [m for m in MARKETS if f"iso_{m}" in oos and f"y_{m}" in oos]
    per_season = {int(s): float(np.nanmean([_ll(d[f"y_{m}"], d[f"iso_{m}"]) for m in ok])) for s, d in oos.groupby("season")}
    return float(np.nanmean([_ll(oos[f"y_{m}"], oos[f"iso_{m}"]) for m in ok])), per_season


def ablation(frame: pd.DataFrame, first_test: int, last_test: int) -> dict:
    from models.nfl_features import all_feature_cols

    base_cols = all_feature_cols(BASE_GROUPS)
    base = walk_forward(frame, base_cols, first_test, last_test, n_estimators=150)
    base_ll, _ = _mean_final_ll(base)
    base_model_ll, base_seasons = _mean_model_ll(base)
    base_rmse = float(np.sqrt(np.nanmean((base["margin"] - base["pred_margin"]) ** 2)))
    report = {"base": {"final_logloss": base_ll, "model_logloss": base_model_ll, "margin_rmse": base_rmse}, "groups": {}}
    for grp in CANDIDATE_GROUPS:
        cols = base_cols + all_feature_cols([grp])
        oos = walk_forward(frame, cols, first_test, last_test, n_estimators=150)
        ll, _ = _mean_final_ll(oos)
        model_ll, seasons = _mean_model_ll(oos)
        rmse = float(np.sqrt(np.nanmean((oos["margin"] - oos["pred_margin"]) ** 2)))
        wins = sum(1 for s in seasons if seasons[s] < base_seasons.get(s, np.inf))
        # keep on out-of-sample improvement of the model's own log loss (the
        # market-stacked number barely moves when the model weight is small)
        delta_model = model_ll - base_model_ll
        keep = bool(delta_model < 0 and wins >= len(seasons) / 2)
        report["groups"][grp] = {"final_logloss": ll, "delta_final": ll - base_ll, "model_logloss": model_ll,
                                 "delta_model": delta_model, "margin_rmse": rmse, "delta_rmse": rmse - base_rmse,
                                 "seasons_improved": wins, "seasons": len(seasons), "keep": keep,
                                 "features": all_feature_cols([grp])}
        print(f"  ablation {grp:<16} Δmodel_ll={delta_model:+.5f} Δfinal_ll={ll - base_ll:+.5f} "
              f"Δrmse={rmse - base_rmse:+.3f} improved {wins}/{len(seasons)} -> {'KEEP' if keep else 'drop'}")
    report["kept"] = [g for g, v in report["groups"].items() if v["keep"]]
    report["dropped"] = [g for g, v in report["groups"].items() if not v["keep"]]
    return report


def run_backtest(league: str, quick: bool = False) -> dict:
    if league != "NFL":
        from edgecard.nba import run_nba_backtest

        return run_nba_backtest(quick=quick)
    from models.nfl_features import all_feature_cols

    frame = load_nfl_frame()
    latest = int(frame.loc[frame["is_final"], "season"].max())
    first_test = latest - (2 if quick else 6)
    print(f"NFL backtest: test seasons {first_test}-{latest}")
    abl = ablation(frame, first_test, latest)
    groups = BASE_GROUPS + abl["kept"]
    cols = all_feature_cols(groups)
    oos = walk_forward(frame, cols, first_test, latest)
    summ = summarize(oos, frame)
    verdicts = _verdicts(summ)

    # production fit: everything final, calibrators on all OOS rows
    all_oos = walk_forward(frame, cols, first_test - 1, latest, n_estimators=150) if not quick else oos
    resid = pd.DataFrame({"resid_margin": all_oos["margin"] - all_oos["pred_margin"],
                          "resid_total": all_oos["total_pts"] - all_oos["pred_total"],
                          "pred_margin": all_oos["pred_margin"], "pred_total": all_oos["pred_total"],
                          "margin": all_oos["margin"], "total_pts": all_oos["total_pts"]})
    gm = GameModel(cols).fit(frame[frame["is_final"]], oos_resid=resid)
    cal = Calibrators.fit(oos)
    with open(store.path("models", "nfl_game.pkl"), "wb") as f:
        pickle.dump({"model": gm, "calibrators": cal, "groups": groups, "trained_at": dt.datetime.utcnow().isoformat(),
                     "trained_through": str(frame.loc[frame["is_final"], "game_date"].max())}, f)

    report = {"league": "NFL", "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
              "test_seasons": [first_test, latest], "n_games_oos": int(len(oos)), "feature_groups_used": groups,
              "ablation": abl, "summary": summ, "stack_coefficients": cal.stack_coef, "verdicts": verdicts,
              "joint_rho_fav": gm.joint.rho_fav, "sigma_margin": [gm.sigma_margin.a, gm.sigma_margin.b],
              "sigma_total": [gm.sigma_total.a, gm.sigma_total.b]}
    store.write_json(report, "reports", "backtest_nfl.json")
    oos.to_parquet(store.path("reports", "backtest_nfl_oos.parquet"), index=False)
    try:  # props calibration vs real outcomes (last two seasons)
        from edgecard.props_backtest import run_props_backtest

        run_props_backtest(seasons=(latest - 1,) if quick else (latest - 2, latest - 1), n_sims=2000)
    except Exception as exc:  # noqa: BLE001
        print(f"props backtest failed: {exc}")
    print(json.dumps({"verdicts": verdicts, "kept": abl["kept"], "dropped": abl["dropped"],
                      "betting_at_close": summ["betting_at_close"]}, indent=1, default=str))
    return report


def _verdicts(summ: dict) -> list[str]:
    out = []
    names = {"ml_home": "moneyline", "spread_home": "spread", "over": "total"}
    for m, r in summ["markets"].items():
        if not r.get("n"):
            out.append(f"{names[m]}: no historical market lines yet — cannot compare to the closing line (not bet).")
            continue
        fm = r.get("final_minus_market_logloss")
        mm = r.get("model_minus_market_logloss")
        if fm is None or np.isnan(fm):
            continue
        if fm < -0.001:
            out.append(f"{names[m]}: final probability beat the no-vig closing line out of sample "
                       f"(log loss {r['logloss_final']:.4f} vs {r['logloss_mkt']:.4f}).")
        else:
            out.append(f"{names[m]}: did NOT beat the no-vig closing line out of sample "
                       f"(final {r['logloss_final']:.4f} vs market {r['logloss_mkt']:.4f}; model alone "
                       f"{r['logloss_iso']:.4f}). Edges in this market should be treated as noise.")
        if mm is not None and not np.isnan(mm) and mm > 0:
            out.append(f"{names[m]}: the model on its own is worse than the market by {mm:.4f} log loss.")
    b = summ.get("betting_at_close", {})
    if b.get("n_bets"):
        ci = b.get("roi_ci95", [np.nan, np.nan])
        out.append(f"Flat bets at closing prices when edge >= {EDGE_THRESHOLD:.0%}: {b['n_bets']} bets, ROI {b['roi']:+.1%} "
                   f"(95% CI {ci[0]:+.1%} to {ci[1]:+.1%}).")
        if ci[0] <= 0:
            out.append("That ROI interval includes zero or losses: no statistically reliable profit shown.")
    else:
        out.append("No historical bets cleared the edge threshold: the model never disagreed with the close enough to act.")
    return out

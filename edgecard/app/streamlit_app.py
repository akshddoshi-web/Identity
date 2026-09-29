"""Edge Card — Streamlit viewer.

Read-only: it never computes a card. GitHub Actions builds the card and
commits the results to the `edgecard-data` branch; this page reads those
files (over raw.githubusercontent.com, or a local store when
EDGECARD_DATA_DIR is set) so it loads in about a second.

Password: set APP_PASSWORD in Streamlit Cloud -> App settings -> Secrets.
"""
from __future__ import annotations

import hmac
import io
import json
import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Edge Card", page_icon="🃏", layout="wide")

REPO = os.environ.get("EDGECARD_REPO", "akshddoshi-web/Identity")
BRANCH = os.environ.get("EDGECARD_DATA_BRANCH", "edgecard-data")
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
LOCAL = os.environ.get("EDGECARD_DATA_DIR")


# --------------------------------------------------------------------------- #
# password gate
# --------------------------------------------------------------------------- #

def _secret(name: str) -> str | None:
    try:
        return st.secrets.get(name)
    except Exception:  # noqa: BLE001 — no secrets file locally
        return os.environ.get(name)


def check_password() -> bool:
    expected = _secret("APP_PASSWORD")
    if not expected:
        st.error("APP_PASSWORD is not configured. Add it under App settings → Secrets. The page stays locked until then.")
        return False
    if st.session_state.get("auth_ok"):
        return True
    st.title("🃏 Edge Card")
    pw = st.text_input("Password", type="password")
    if pw:
        if hmac.compare_digest(pw.encode(), str(expected).encode()):
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Wrong password.")
    return False


if not check_password():
    st.stop()


# --------------------------------------------------------------------------- #
# data access
# --------------------------------------------------------------------------- #

@st.cache_data(ttl=300, show_spinner=False)
def fetch_bytes(path: str) -> bytes | None:
    if LOCAL:
        p = Path(LOCAL) / path
        return p.read_bytes() if p.exists() else None
    r = requests.get(f"{RAW}/{path}", timeout=15)
    return r.content if r.ok else None


def get_json(path: str):
    b = fetch_bytes(path)
    return json.loads(b) if b else None


def get_csv(path: str) -> pd.DataFrame:
    b = fetch_bytes(path)
    return pd.read_csv(io.BytesIO(b)) if b else pd.DataFrame()


# --------------------------------------------------------------------------- #
# layout
# --------------------------------------------------------------------------- #

card = get_json("cards/latest.json")
st.title("🃏 Edge Card")
if card is None:
    st.info("No card has been published yet. The first scheduled run (≈10:00 ET) will create one.")
    st.stop()

mode_badge = "📝 PAPER MODE" if card.get("paper_mode", True) else "💵 LIVE"
st.caption(f"{mode_badge} · published {card.get('generated_at_et')} ({card.get('mode')} run) · "
           f"bankroll ${card.get('bankroll', 0):,.0f} · {card.get('disclaimer', '')}")
for w in card.get("warnings", []):
    st.error(w)

tab_card, tab_track, tab_bt, tab_props, tab_fresh = st.tabs(["Today's card", "Tracking", "Backtest", "Props (shadow)", "Data freshness"])

TIER_ICON = {"SAFE": "🟢", "MODERATE": "🟡", "LONG SHOT": "🔴"}

with tab_card:
    leagues = card.get("leagues", {})
    if not leagues:
        st.write("No leagues in this card.")
    for lg, c in leagues.items():
        st.subheader(f"{lg} · {c.get('n_games', 0)} games in window")
        if c.get("error"):
            st.warning(f"Card build error: {c['error']}")
        if c.get("model", {}).get("note"):
            st.caption(f"Model: {c['model']['note']}")
        cols = st.columns(3)
        for col, tier in zip(cols, ("SAFE", "MODERATE", "LONG SHOT")):
            v = c.get("tiers", {}).get(tier, {})
            with col:
                st.markdown(f"#### {TIER_ICON[tier]} {tier}")
                if not v or v.get("id") is None:
                    st.markdown(f"**{v.get('message', 'NO BET')}**")
                    if v.get("reason"):
                        st.caption(v["reason"])
                    continue
                status = v["status"]
                if status == "WAIT":
                    ts = pd.Timestamp(v["recheck_at"]).tz_convert("America/New_York").strftime("%a %I:%M %p ET")
                    st.warning(f"WAIT — recheck after {ts}")
                st.markdown(f"**{v['description']}**")
                st.markdown(f"Best book: **{v['book']}** at **{v['price']:+d}** · don't take worse than **{v['min_acceptable_price']:+d}**")
                m1, m2, m3 = st.columns(3)
                m1.metric("Model prob", f"{v['model_prob']:.1%}")
                m2.metric("No-vig market", f"{v['novig_market_prob']:.1%}")
                m3.metric("Edge", f"{v['edge']:+.1%}")
                m4, m5, m6 = st.columns(3)
                m4.metric("EV / $100", f"${v['ev_per_100']:+.2f}")
                m5.metric("Stake", f"${v['stake']:,.2f}")
                m6.metric("Legs", len(v["legs"]))
                st.markdown("**Why (quantified)**")
                for r in v.get("reasons", [])[:3]:
                    st.markdown(f"- {r}")
                for n in v.get("notes", []):
                    st.caption(n)
                with st.expander(f"News & injury flags checked ({len(v.get('flags', []))})"):
                    if not v.get("flags"):
                        st.write("No flags on the players/teams involved.")
                    for f in v.get("flags", []):
                        src = f"[{f['source']}]({f['url']})" if f.get("url") else f["source"]
                        st.markdown(f"- **{f['flag_type']}** (severity {f['severity']}) {f.get('player') or ''}: "
                                    f"{f['text']} — {src}, {str(f['timestamp'])[:16]}")
                with st.expander("Legs"):
                    st.dataframe(pd.DataFrame(v["legs"])[["label", "game", "kickoff", "book", "price", "p_final", "novig_implied", "p_model"]],
                                 hide_index=True, width="stretch")
        st.divider()

with tab_track:
    rep = get_json("reports/weekly.json") or {}
    st.markdown(f"**{rep.get('headline', 'No settled bets yet.')}**")
    if rep.get("warning"):
        st.error(rep["warning"])
    for window in ("last_7_days", "all_time"):
        if window in rep:
            st.markdown(f"##### {window.replace('_', ' ').title()}")
            o = rep[window]["overall"]
            if o.get("n"):
                a, b, c_, d = st.columns(4)
                a.metric("Settled", o["n"])
                b.metric("ROI", f"{(o['roi'] or 0):+.1%}")
                c_.metric("Mean CLV", f"{(o['mean_clv'] or 0):+.2%}")
                d.metric("Brier", f"{o['brier']:.3f}")
                for dim in ("by_tier", "by_bet_type", "by_league"):
                    df = pd.DataFrame(rep[window][dim]).T
                    if not df.empty:
                        st.caption(dim.replace("_", " "))
                        st.dataframe(df, width="stretch")
    if rep.get("calibration"):
        cal = pd.DataFrame(rep["calibration"])
        st.markdown("##### Calibration (settled bets)")
        st.line_chart(cal.set_index("pred")[["actual"]])
        st.dataframe(cal, hide_index=True)
    recs = get_csv("ledger/recommendations.csv")
    if not recs.empty:
        st.markdown("##### Every recommendation (append-only log)")
        st.dataframe(recs.drop(columns=["legs_json"], errors="ignore").sort_values("created_at", ascending=False),
                     hide_index=True, width="stretch")

with tab_bt:
    for lg in ("nfl", "nba"):
        bt = get_json(f"reports/backtest_{lg}.json")
        if not bt:
            st.info(f"{lg.upper()}: no backtest published yet.")
            continue
        st.subheader(f"{lg.upper()} walk-forward backtest · seasons {bt['test_seasons'][0]}–{bt['test_seasons'][1]} · {bt['n_games_oos']} games")
        for v in bt.get("verdicts", []):
            st.markdown(f"- {v}")
        abl = bt.get("ablation", {})
        st.markdown(f"**Situational features kept:** {', '.join(abl.get('kept', [])) or 'none'}  \n"
                    f"**Dropped (no out-of-sample lift):** {', '.join(abl.get('dropped', [])) or 'none'}")
        g = pd.DataFrame(abl.get("groups", {})).T
        if not g.empty:
            st.dataframe(g[["delta_model", "delta_final", "delta_rmse", "seasons_improved", "seasons", "keep"]], width="stretch")
        mk = bt["summary"]["markets"]
        tbl = pd.DataFrame({m: {k: v for k, v in r.items() if isinstance(v, (int, float))} for m, r in mk.items()}).T
        st.dataframe(tbl, width="stretch")
        for m, r in mk.items():
            if r.get("calibration_model"):
                cal = pd.DataFrame(r["calibration_model"])
                st.caption(f"Calibration — model only — {m}")
                st.line_chart(cal.set_index("pred")[["actual"]])
        st.caption(f"Model weight vs market (w, fitted out of sample): {json.dumps(bt.get('stack_coefficients', {}))}")
    pb = get_json("reports/backtest_nfl_props.json")
    if pb:
        st.subheader("NFL props — calibration vs real outcomes (no historical prop prices exist for free)")
        st.dataframe(pd.DataFrame(pb["markets"]).T, width="stretch")

with tab_props:
    for lg, c in card.get("leagues", {}).items():
        sp = c.get("shadow_props") or {}
        st.subheader(lg)
        st.caption(sp.get("status", ""))
        if sp.get("rows"):
            st.dataframe(pd.DataFrame(sp["rows"]), hide_index=True, width="stretch")

with tab_fresh:
    fr = card.get("freshness") or get_json("freshness/latest.json") or {}
    if fr:
        df = pd.DataFrame(fr).T.reset_index().rename(columns={"index": "source"})
        st.dataframe(df, hide_index=True, width="stretch")
    st.caption(f"Data: {RAW if not LOCAL else LOCAL}")

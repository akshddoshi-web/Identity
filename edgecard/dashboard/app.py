"""Streamlit reporting dashboard.

Run with: streamlit run dashboard/app.py

Reads everything from the SQLite DB populated by data_pipeline/ + logged by
guardrails/prediction_log.py — this dashboard renders what actually happened
(or, on synthetic data, what the demo pipeline logged), never a retroactive
recomputation of "what the model would have said."
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_pipeline.config import load_config, db_path
from data_pipeline.db import connect
from edge.clv_tracker import clv_by_sport_and_market, summarize_clv
from bankroll.bankroll_tracker import compute_equity_curve, compute_bankroll_stats, bankroll_headline
from bankroll.monte_carlo import simulate_bankroll_paths, paths_to_dataframe
from guardrails.disclaimers import (
    TOP_LEVEL_DISCLAIMER,
    VARIANCE_REALITY_CHECK,
    NO_PARLAY_POLICY,
    small_sample_warning,
    confidence_caveat,
)
from scripts.daily_report import run_daily_report, flags_to_dataframe, SPORTS as REPORT_SPORTS

# --- validated categorical palette (dataviz skill reference palette), fixed order ---
SPORT_COLOR = {"NFL": "#2a78d6", "NCAAF": "#eb6834", "NBA": "#1baf7a"}
SEQ_BLUE = "#256abf"
DIVERGING_POS = "#2a78d6"
DIVERGING_NEG = "#e34948"
MUTED = "#898781"
GRID = "#e1e0d9"
WARNING = "#fab219"

st.set_page_config(page_title="Sports Betting Analytics", layout="wide")

cfg = load_config()
MIN_SIG_N = cfg["edge_detection"]["min_sample_size_for_significance"]


@st.cache_data(ttl=60)
def load_predictions() -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(
            """SELECT p.*, g.home_team, g.away_team, g.game_date, g.home_score, g.away_score
               FROM predictions p JOIN games g ON g.game_id = p.game_id
               ORDER BY p.predicted_at DESC""",
            conn,
        )


@st.cache_data(ttl=60)
def load_ledger() -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(
            """SELECT bl.*, p.sport, p.market FROM bet_ledger bl
               JOIN predictions p ON p.prediction_id = bl.prediction_id
               ORDER BY bl.placed_at""",
            conn,
        )


@st.cache_data(ttl=60)
def load_clv_breakdown() -> pd.DataFrame:
    with connect() as conn:
        return clv_by_sport_and_market(conn, cfg)


st.title("Sports Betting Analytics — Decision Support Dashboard")

st.warning(TOP_LEVEL_DISCLAIMER)
with st.expander("More on variance and scope (read before trusting any number below)"):
    st.write(VARIANCE_REALITY_CHECK)
    st.write(NO_PARLAY_POLICY)

try:
    predictions_df = load_predictions()
    ledger_df = load_ledger()
    clv_df = load_clv_breakdown()
except Exception as e:
    st.error(
        f"Could not read the database ({e}). Run `python scripts/ingest_real_data.py` "
        "(or, for a pipeline-mechanics-only smoke test, `python scripts/generate_sample_data.py` "
        "+ `python scripts/run_pipeline_demo.py`) first."
    )
    st.stop()

sports_present = sorted(predictions_df["sport"].unique()) if not predictions_df.empty else []
sport_filter = st.sidebar.multiselect("Sport", options=sports_present, default=sports_present)

with st.sidebar:
    st.divider()
    st.caption(
        "On Streamlit Community Cloud, this app's local database is NOT guaranteed to survive "
        "a redeploy or a sleep/wake cycle — download a backup periodically if you're logging "
        "real predictions here and want to keep them."
    )
    try:
        with open(db_path(cfg), "rb") as f:
            st.download_button("Download database backup", f.read(), file_name="betting_backup.db", mime="application/octet-stream")
    except FileNotFoundError:
        pass

pred_view = predictions_df[predictions_df["sport"].isin(sport_filter)] if sport_filter else predictions_df
ledger_view = ledger_df[ledger_df["sport"].isin(sport_filter)] if sport_filter else ledger_df
clv_view = clv_df[clv_df["sport"].isin(sport_filter)] if sport_filter else clv_df

tab_today, tab_overview = st.tabs(["📋 Today's Bets", "📊 Model, CLV & Bankroll"])

# =============================================================================
# TODAY'S BETS
# =============================================================================
with tab_today:
    st.warning(TOP_LEVEL_DISCLAIMER)

    st.subheader("Today's flagged edges")
    st.caption(
        "Runs scripts/daily_report.py: pulls today's live pre-game odds, runs each game "
        "through the trained production models, de-vigs the market line, and flags games "
        "where the model's probability clears the configured edge threshold "
        f"({cfg['edge_detection']['min_edge_threshold']:.1%}). "
        "**Clicking the button below logs any flagged predictions to the immutable, "
        "timestamped pre-game guardrail log (guardrails/prediction_log.py) — this is the "
        "real thing, not a preview.** Re-running later the same day for the same games is "
        "safe (already-logged predictions are recognized, not re-logged or duplicated)."
    )

    run_clicked = st.button("Run today's report", type="primary")
    if run_clicked:
        st.session_state.pop("daily_report_result", None)
        st.session_state.pop("daily_report_error", None)
        progress_box = st.empty()

        def _progress(sport, message):
            progress_box.info(f"**{sport}**: {message}")

        try:
            with st.spinner("Training production models and pulling live odds — this can take a minute or two..."):
                st.session_state["daily_report_result"] = run_daily_report(cfg, progress_cb=_progress)
        except RuntimeError as e:
            st.session_state["daily_report_error"] = str(e)
        progress_box.empty()

    if "daily_report_error" in st.session_state:
        st.error(
            f"{st.session_state['daily_report_error']}\n\n"
            "Set ODDS_API_KEY (a local `.env` file, or — on Streamlit Community Cloud — "
            "Settings -> Secrets) before running this. See README's 'Odds API key setup'."
        )
    elif "daily_report_result" not in st.session_state:
        st.info("Click **Run today's report** to pull live odds and check today's slate for edges.")
    else:
        result = st.session_state["daily_report_result"]

        st.markdown(f"**{bankroll_headline(result['bankroll_stats'], result['min_sig_n'])}**")
        warn = small_sample_warning(result["bankroll_stats"].n_bets, result["min_sig_n"])
        if warn:
            st.markdown(f"⚠️ {warn}")

        for sport in REPORT_SPORTS:
            if sport in result["skipped"]:
                st.markdown(f"- **{sport}**: skipped — {result['skipped'][sport]}")

        report_df = flags_to_dataframe(result["flags"])
        if report_df.empty:
            st.success(
                f"No games cleared the {result['threshold']:.1%} edge threshold today across the sports "
                "checked. No bets are being suggested — the bar is not lowered to manufacture picks."
            )
        else:
            st.markdown(f"**{len(report_df)} game/market combination(s) cleared the {result['threshold']:.1%} edge threshold:**")
            display_df = report_df.copy()
            display_df["edge_pct"] = display_df["edge_pct"].map(lambda x: f"{x:+.1%}")
            display_df["suggested_stake"] = display_df["suggested_stake"].map(lambda x: f"${x:,.2f}")
            st.dataframe(display_df, width="stretch", hide_index=True)

            csv_bytes = report_df.to_csv(index=False).encode("utf-8")
            st.download_button("Download as CSV", csv_bytes, file_name="daily_report.csv", mime="text/csv")

    st.divider()
    st.caption(VARIANCE_REALITY_CHECK)
    st.caption(NO_PARLAY_POLICY)

# =============================================================================
# MODEL, CLV & BANKROLL (previously the whole dashboard body)
# =============================================================================
with tab_overview:
    st.header("1. Model vs. market probability — recent flagged predictions")
    st.caption(
        "Every row here was logged BEFORE its game started (see guardrails/prediction_log.py) — "
        "nothing is retroactively added. These are predictions actually logged by "
        "scripts/daily_report.py (Today's Bets tab) or scripts/run_pipeline_demo.py, not a "
        "live re-computation."
    )

    if pred_view.empty:
        st.info("No predictions logged yet.")
    else:
        show_cols = [
            "sport", "home_team", "away_team", "game_date", "market",
            "model_prob_home", "market_devigged_prob_home", "edge", "predicted_at",
        ]
        st.dataframe(
            pred_view[show_cols].head(50).style.format(
                {"model_prob_home": "{:.1%}", "market_devigged_prob_home": "{:.1%}", "edge": "{:+.1%}"}
            ),
            width='stretch',
        )

        fig = go.Figure()
        for sport in sport_filter:
            d = pred_view[pred_view["sport"] == sport]
            fig.add_trace(
                go.Scatter(
                    x=d["market_devigged_prob_home"],
                    y=d["model_prob_home"],
                    mode="markers",
                    name=sport,
                    marker=dict(size=8, color=SPORT_COLOR.get(sport, MUTED), line=dict(width=1, color="white")),
                )
            )
        fig.add_trace(
            go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="No edge (model = market)",
                        line=dict(color=MUTED, dash="dash", width=1), hoverinfo="skip")
        )
        fig.update_layout(
            xaxis_title="De-vigged market probability (home)",
            yaxis_title="Model probability (home)",
            xaxis=dict(range=[0, 1], gridcolor=GRID),
            yaxis=dict(range=[0, 1], gridcolor=GRID),
            plot_bgcolor="#fcfcfb",
            paper_bgcolor="#fcfcfb",
            legend_title_text="Sport",
            height=450,
        )
        st.plotly_chart(fig, width='stretch')

    st.header("2. Historical CLV performance by sport and bet type")
    st.caption(
        "Closing Line Value: de-vigged closing probability minus the probability implied by the "
        "price actually taken. Positive and consistent beats short-run win rate as evidence of "
        "skill — see the explainer in guardrails/disclaimers.py."
    )

    if clv_view.empty:
        st.info("No settled CLV records yet.")
    else:
        clv_view = clv_view.copy()
        clv_view["label"] = clv_view["sport"] + " — " + clv_view["market"]
        colors = [SPORT_COLOR.get(s, MUTED) for s in clv_view["sport"]]
        err_plus = clv_view["ci_high"] - clv_view["mean_clv_pct"]
        err_minus = clv_view["mean_clv_pct"] - clv_view["ci_low"]

        fig2 = go.Figure(
            go.Bar(
                x=clv_view["label"],
                y=clv_view["mean_clv_pct"],
                marker_color=colors,
                error_y=dict(type="data", symmetric=False, array=err_plus, arrayminus=err_minus, color=MUTED),
            )
        )
        fig2.add_hline(y=0, line_color=MUTED, line_width=1)
        fig2.update_layout(
            yaxis_title="Mean CLV (probability points)",
            yaxis=dict(tickformat="+.1%", gridcolor=GRID),
            xaxis=dict(gridcolor=GRID),
            plot_bgcolor="#fcfcfb",
            paper_bgcolor="#fcfcfb",
            height=420,
        )
        st.plotly_chart(fig2, width='stretch')

        for _, row in clv_view.iterrows():
            warn = small_sample_warning(int(row["n"]), MIN_SIG_N)
            caveat = confidence_caveat(row["ci_low"], row["ci_high"], int(row["n"]))
            if warn:
                st.markdown(f"⚠️ **{row['label']}** — {warn}")
            else:
                st.markdown(f"✅ **{row['label']}** — {caveat}")

    st.header("3. Bankroll growth, drawdown, and variance-adjusted return")

    if ledger_view.empty:
        st.info("No settled bets in the ledger yet.")
    else:
        starting_bankroll = cfg["bankroll"]["starting_bankroll"]
        bankroll_tabs = st.tabs(sport_filter if sport_filter else ["All"])
        for tab, sport in zip(bankroll_tabs, sport_filter if sport_filter else ["All"]):
            with tab:
                sub = ledger_view[ledger_view["sport"] == sport] if sport != "All" else ledger_view
                if sub.empty:
                    st.info("No settled bets.")
                    continue
                curve = compute_equity_curve(sub, starting_bankroll)
                stats_out = compute_bankroll_stats(sub, starting_bankroll)

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Ending bankroll", f"${stats_out.ending_bankroll:,.0f}", f"{stats_out.roi_pct:+.1%} ROI")
                c2.metric("Max drawdown", f"{stats_out.max_drawdown_pct:.1%}")
                c3.metric("Sharpe-like ratio (per-bet)", f"{stats_out.sharpe_like_ratio:.3f}")
                c4.metric("Settled bets", f"{stats_out.n_bets}")

                if stats_out.n_bets < MIN_SIG_N:
                    st.markdown(f"⚠️ {small_sample_warning(stats_out.n_bets, MIN_SIG_N)}")

                fig3 = go.Figure(
                    go.Scatter(
                        x=list(range(len(curve))), y=curve["bankroll"], mode="lines",
                        line=dict(color=SPORT_COLOR.get(sport, SEQ_BLUE), width=2),
                        fill="tozeroy", fillcolor="rgba(42,120,214,0.08)", name="Bankroll",
                    )
                )
                fig3.add_hline(y=starting_bankroll, line_color=MUTED, line_dash="dash", line_width=1)
                fig3.update_layout(
                    xaxis_title="Settled bet #", yaxis_title="Bankroll ($)",
                    xaxis=dict(gridcolor=GRID), yaxis=dict(gridcolor=GRID),
                    plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb", height=380, showlegend=False,
                )
                st.plotly_chart(fig3, width='stretch')

    st.header("4. Monte Carlo: what variance actually looks like")
    st.caption(
        "A single backtest or a single realized bankroll curve is ONE draw from a much wider "
        "distribution of possible outcomes. This simulates many independent draws at a given "
        "true win probability, price, and stake size."
    )

    mc_col1, mc_col2, mc_col3 = st.columns(3)
    true_win_prob = mc_col1.slider("Assumed true win probability", 0.45, 0.65, 0.55, 0.005, format="%.3f")
    price = mc_col2.slider("Price (American odds)", -200, 150, -110, 5)
    stake_fraction = mc_col3.slider(
        "Stake per bet (% of current bankroll)", 0.005, cfg["kelly"]["max_bet_pct_of_bankroll"], 0.02, 0.005, format="%.3f"
    )

    mc = simulate_bankroll_paths(
        true_win_prob=true_win_prob, price=price, stake_fraction=stake_fraction, cfg=cfg, seed=7
    )
    paths_df = paths_to_dataframe(mc)

    fig4 = go.Figure()
    for sim_id, g in paths_df.groupby("sim_id"):
        fig4.add_trace(
            go.Scatter(
                x=g["bet_index"], y=g["bankroll"], mode="lines",
                line=dict(color=SEQ_BLUE, width=0.6), opacity=0.10, showlegend=False, hoverinfo="skip",
            )
        )
    median_path = paths_df.groupby("bet_index")["bankroll"].median()
    fig4.add_trace(
        go.Scatter(x=median_path.index, y=median_path.values, mode="lines",
                    line=dict(color="#0b0b0b", width=2.5), name="Median path")
    )
    fig4.update_layout(
        xaxis_title="Bet #", yaxis_title="Bankroll ($)",
        xaxis=dict(gridcolor=GRID), yaxis=dict(gridcolor=GRID),
        plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb", height=420,
    )
    st.plotly_chart(fig4, width='stretch')
    st.text(mc.headline())

    st.header("Disclaimers")
    st.info(TOP_LEVEL_DISCLAIMER)

"""
streamlit_app.py — Phase 8R Research Workbench UI.

This file (and only this file) may import Streamlit. It imports exactly one project module:
`src.app.research_application`. It contains no factor/signal/portfolio/backtest logic of its
own — every number shown here comes from a Phase 8A CertifiedResearchRunExecutor run via the
Application Layer. See docs/PHASE_8R_ARCHITECTURE_PROPOSAL.md §3 for the enforced boundary.

Research & Backtest analysis only. No broker connection, no order execution, no live trading,
no automatic buy/sell.
"""

from datetime import date

import streamlit as st

from src.app import research_application as app

st.set_page_config(page_title="Research Workbench", layout="wide")

st.title("📊 Research Workbench")
st.caption(
    "Historical Quantitative Research / Backtest Analysis — **Research & Backtest ONLY**. "
    "No broker connection, no order execution, no live trading, no automatic buy/sell."
)
st.info(
    "Historical backtest results are research outputs and do not guarantee future performance. "
    "This tool does not provide investment advice or automatic trading signals.",
    icon="ℹ️",
)


def _render_provenance_badge(provider_data_origin: dict) -> None:
    origins = set(provider_data_origin.values())
    if "REAL_PROVIDER" in origins:
        st.error("Data marked REAL_PROVIDER — verify this is genuinely live-provider sourced.")
    else:
        st.warning(
            f"**LIVE PROVIDER: NOT VERIFIED** — Reason: `LIVE_PROVIDER_CREDENTIALS_UNAVAILABLE`. "
            f"All data in this run is tagged: {', '.join(sorted(origins))}.",
            icon="⚠️",
        )


def _render_run_detail(run_id: str) -> None:
    try:
        detail = app.get_research_run(run_id)
    except app.ResearchRunError as e:
        st.error(str(e))
        return

    st.subheader(f"Research Run: `{detail.run_id}`")
    st.caption(f"Certification status: **{detail.certification_status}** — created {detail.created_at}")

    _render_provenance_badge(detail.provider_data_origin)

    id_col, metric_col = st.columns(2)
    with id_col:
        st.markdown("**Identity**")
        st.table({
            "Field": ["Dataset ID", "Dataset Version", "Dataset SHA-256", "Snapshot ID", "As-of",
                      "Code Version", "Code State", "Result Hash"],
            "Value": [detail.dataset_id, detail.dataset_version, detail.dataset_sha256[:24] + "...",
                      detail.snapshot_id, detail.as_of, detail.code_version[:12], detail.code_state,
                      detail.result_hash[:24] + "..."],
        })
    with metric_col:
        st.markdown("**Backtest Result**")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Return", f"{detail.total_return:.2%}")
        m2.metric("Sharpe Ratio", f"{detail.sharpe_ratio:.4f}")
        m3.metric("Max Drawdown", f"{detail.max_drawdown:.2%}")
        m4, m5, m6 = st.columns(3)
        m4.metric("Annualized Return", f"{detail.annualized_return:.2%}")
        m5.metric("Annualized Volatility", f"{detail.annualized_volatility:.2%}")
        m6.metric("Win Rate", f"{detail.win_rate:.2%}")

    st.markdown("**Universe**")
    st.write(", ".join(detail.universe_symbols))

    st.markdown("**Factor Configuration** (bound into `factor_definition_hash`)")
    st.json([f["factor_id"] for f in detail.factor_definitions])
    st.caption(f"factor_definition_hash: `{detail.factor_definition_hash}`")

    st.markdown("**Signal Configuration** (bound into `signal_configuration_hash`)")
    st.json(detail.signal_config)
    st.caption(f"signal_configuration_hash: `{detail.signal_configuration_hash}`")

    st.markdown("**Research Portfolio / Historical Target Weights** _(not a live or trading portfolio)_")
    if detail.portfolio_weights:
        st.bar_chart(detail.portfolio_weights)
        st.table(detail.portfolio_weights)
    else:
        st.write("_Fully cash — no positions selected by the strategy for this run._")

    with st.expander("Corporate actions applied (PIT-filtered)"):
        st.json(detail.corporate_actions_applied)

    with st.expander("⚠️ Known limitations"):
        for item in detail.limitations:
            st.write(f"- {item}")

    st.markdown("---")
    replay_col, report_col = st.columns(2)
    with replay_col:
        if st.button("🔁 Replay this Research Run", key=f"replay_{run_id}"):
            replay = app.replay_research_run(run_id)
            if replay.status == "REPRODUCIBLE":
                st.success(f"REPRODUCIBLE — {replay.explanation}")
            elif replay.status == "INTERMEDIATE_ARTIFACT_MISMATCH":
                st.error(f"INTERMEDIATE_ARTIFACT_MISMATCH — {replay.explanation}")
            elif replay.status == "FINAL_RESULT_MISMATCH":
                st.error(f"FINAL_RESULT_MISMATCH — {replay.explanation}")
            else:
                st.error(f"{replay.status} — {replay.explanation}")
    with report_col:
        report_state_key = f"report_content_{run_id}"  # distinct from any widget's own key
        if st.button("📄 Generate Research Report", key=f"report_button_{run_id}"):
            st.session_state[report_state_key] = app.generate_research_report(run_id)
        if report_state_key in st.session_state:
            st.download_button(
                "Download report (Markdown)", data=st.session_state[report_state_key],
                file_name=f"{run_id}_report.md", mime="text/markdown", key=f"dl_{run_id}",
            )
            with st.expander("Preview report"):
                st.markdown(st.session_state[report_state_key])


page = st.sidebar.radio("Navigate", ["New Research Run", "Research Run History"])

if page == "New Research Run":
    st.header("1. Configure Research Run")

    as_of_range = app.get_available_as_of_range()
    min_as_of = date.fromisoformat(as_of_range["min_as_of"])
    max_as_of = date.fromisoformat(as_of_range["max_as_of"])

    selected_as_of = st.date_input(
        "Historical as-of date", value=max_as_of, min_value=min_as_of, max_value=max_as_of,
        help="The certified GOLDEN_DATASET covers this date range only.",
    )

    universe_view = app.get_universe(selected_as_of)
    st.caption(universe_view.note)
    symbol_options = [s.symbol for s in universe_view.symbols if s.tradable_as_of]
    symbol_labels = {s.symbol: f"{s.symbol} — {s.display_name}" for s in universe_view.symbols}
    selected_symbols = st.multiselect(
        "Historical Universe", options=symbol_options,
        default=symbol_options, format_func=lambda s: symbol_labels.get(s, s),
    )

    factor_views = app.get_factor_definitions()
    st.markdown("**Factor Configuration**")
    selected_factors = []
    for f in factor_views:
        checked = st.checkbox(f"{f.factor_id} — {f.description}", value=True, key=f"factor_{f.factor_id}")
        if checked:
            selected_factors.append(f.factor_id)

    top_n = st.number_input("Top N (portfolio size)", min_value=1, max_value=max(1, len(symbol_options)), value=2)
    commission_rate = st.number_input(
        "Commission rate", min_value=0.0, max_value=0.05, value=0.0003, step=0.0001, format="%.4f"
    )

    st.header("2. Run")
    if st.button("▶ Run Research", type="primary"):
        params = app.ResearchRunParams(
            as_of=selected_as_of, universe_symbols=selected_symbols, factor_ids=selected_factors,
            top_n=int(top_n), commission_rate=float(commission_rate),
        )
        try:
            detail = app.create_research_run(params)
            st.session_state["last_run_id"] = detail.run_id
            st.success(f"Research Run certified: `{detail.run_id}`")
        except app.ResearchRunError as e:
            st.error(f"FAIL CLOSED — this research run could not be certified: {e}")

    if "last_run_id" in st.session_state:
        st.markdown("---")
        _render_run_detail(st.session_state["last_run_id"])

elif page == "Research Run History":
    st.header("Research Run History")
    runs = app.list_research_runs()
    if not runs:
        st.write("No research runs yet — create one under **New Research Run**.")
    else:
        options = {r.run_id: f"{r.run_id}  ({r.as_of}, {', '.join(r.factor_ids)}, return={r.total_return:.2%})" for r in runs}
        selected = st.selectbox("Select a Research Run", options=list(options.keys()), format_func=lambda k: options[k])
        if selected:
            st.markdown("---")
            _render_run_detail(selected)

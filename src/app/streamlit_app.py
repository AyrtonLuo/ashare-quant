"""
streamlit_app.py — Phase 8R Research Workbench UI.

This file (and only this file) may import Streamlit. It imports project code ONLY through the
Application Layer — `src.app.research_application` (Phase 8R workbench) and
`src.app.research_analyst_application` (AI Research Analyst, proposal §9 / §11 step 6). It
contains no factor/signal/portfolio/backtest/evidence/LLM logic of its own; every value shown
here is produced by an Application Layer function. See docs/PHASE_8R_ARCHITECTURE_PROPOSAL.md §3
for the enforced boundary and AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md §9 for the
analyst page's design.

Research & Backtest analysis only. No broker connection, no order execution, no live trading,
no automatic buy/sell.
"""

import os
import sys
from datetime import date

# Deployment bootstrap. `streamlit run src/app/streamlit_app.py` puts THIS file's directory on
# sys.path, not the repository root — so `from src.app import ...` fails with
# ModuleNotFoundError under the `streamlit` console script, which is how Streamlit Community
# Cloud launches an app. (It happens to work locally only when launched as
# `python -m streamlit`, which additionally places the CWD on sys.path.) Resolving the repo root
# from __file__ rather than a CWD or an absolute path keeps this correct under every launcher
# and on any machine.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import streamlit as st

from src.app import research_analyst_application as analyst
from src.app import research_application as app
from src.app import terminal_application as terminal

st.set_page_config(page_title="AI Quant Terminal", layout="wide")


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


def _render_evidence_bundle(bundle) -> None:
    st.markdown("**Evidence Bundle** — every fact and number in the report traces to an item here")
    st.caption(
        f"`{bundle.item_count}` item(s) · evidence_bundle_hash: "
        f"`{bundle.evidence_bundle_hash[:24]}...` · data origin: {bundle.data_origin_breakdown}"
    )
    st.table({
        "Category": [c.category for c in bundle.categories],
        "Status": ["AVAILABLE" if c.available else "NOT AVAILABLE" for c in bundle.categories],
        "Items": [c.item_count for c in bundle.categories],
        "Data origin": [", ".join(c.data_origins) if c.data_origins else "—"
                        for c in bundle.categories],
    })
    for category in bundle.categories:
        if not category.available:
            st.warning(f"**{category.category}: NOT AVAILABLE** — {category.reason}", icon="⚠️")

    with st.expander(f"View all {bundle.item_count} evidence item(s)"):
        st.json([
            {
                "evidence_id": i.evidence_id, "category": i.category, "kind": i.kind,
                "event_date": i.event_date, "source": i.source, "data_origin": i.data_origin,
                "content": i.content,
            }
            for i in bundle.items
        ])


def _render_data_confidence(dc) -> None:
    st.markdown("**Data Confidence** _(a computed metric — never an AI self-rating)_")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Score", f"{dc.score:.4f}")
    c2.metric("Band", dc.band)
    c3.metric("REAL_PROVIDER ratio", f"{dc.real_provider_ratio:.0%}")
    c4.metric("Unresolved conflicts", dc.unresolved_conflict_count)
    st.caption(f"Computed by: `{dc.computed_by}` · sub-scores: {dc.components}")
    st.caption(
        f"FACT={dc.fact_count} · MODEL_OUTPUT={dc.model_output_count} · "
        f"median evidence age={dc.median_evidence_age_days} day(s) · "
        f"origins={dc.origin_breakdown}"
    )
    if dc.missing_categories:
        st.warning(
            "Categories with no evidence (reported, never estimated): "
            + ", ".join(dc.missing_categories),
            icon="⚠️",
        )
    st.caption(f"Conflict detection scope: {dc.conflict_detection_scope}")


def _render_analyst_report(view) -> None:
    st.subheader(f"AI Research Report: `{view.report_id}`")
    if view.narrative_warning:
        st.error(f"**{view.narrative_origin}** — {view.narrative_warning}")
    st.info(view.disclaimer, icon="ℹ️")

    st.markdown("**Provenance**")
    st.table({
        "Field": ["Symbol", "As-of", "Generated at", "Provider", "Model", "Model version",
                  "Prompt version", "Evidence bundle hash", "Code version", "Research run",
                  "Reproducibility scope"],
        "Value": [view.symbol, view.as_of, view.generated_at, view.provider_id, view.model,
                  view.model_version, view.prompt_version,
                  view.evidence_bundle_hash[:24] + "...",
                  f"{view.code_version[:12]} ({view.code_state})",
                  view.research_run_id or "— (not linked to a certified run)",
                  view.reproducibility_scope],
    })
    if view.evidence_integrity_verified:
        st.success("Evidence integrity VERIFIED — the stored bundle still hashes to "
                   "`evidence_bundle_hash`.")
    else:
        st.error("Evidence integrity FAILED — the stored Evidence Bundle no longer matches "
                 "`evidence_bundle_hash`.")

    _render_data_confidence(view.data_confidence)

    if view.conflicts:
        st.markdown("**Unresolved evidence conflicts** _(surfaced, never resolved)_")
        st.table({
            "Category": [c.category for c in view.conflicts],
            "Event date": [c.event_date for c in view.conflicts],
            "Key": [c.key_repr for c in view.conflicts],
            "Evidence": [", ".join(c.evidence_ids) for c in view.conflicts],
            "Detection": [c.detection for c in view.conflicts],
        })

    st.markdown("---")
    for section in view.sections:
        st.markdown(f"### {section.number}. {section.title}  `[{section.content_type}]`")
        if section.is_missing_data:
            st.warning(section.body, icon="⚠️")
        else:
            st.write(section.body)
        if section.evidence_ids:
            st.caption(f"Evidence: {', '.join(section.evidence_ids)}")
        if section.suppressed_ai_body is not None:
            with st.expander("Narrative withheld for this section (retained, not discarded)"):
                st.write(section.suppressed_ai_body)

    _render_evidence_bundle(view.evidence)

    with st.expander("⚠️ Known limitations"):
        for item in view.limitations:
            st.write(f"- {item}")

    st.download_button(
        "Download report (Markdown)", data=view.markdown,
        file_name=f"{view.report_id}.md", mime="text/markdown",
        key=f"dl_analyst_{view.report_id}",
    )


# =================================================================================================
# Terminal mode — consumer view. Plain language only: no PIT, hash, evidence id or research
# identity vocabulary appears on this page. The guarantees behind it are unchanged.
# =================================================================================================

def _render_terminal_quote(quote) -> None:
    if quote.is_demo:
        st.warning(f"**{quote.data_status}** — {quote.demo_notice}", icon="⚠️")
    else:
        st.success(f"**{quote.data_status}** — 实时行情，{quote.data_source}。", icon="✅")

    st.subheader(f"{quote.display_name}　{quote.symbol}")
    price_col, change_col, volume_col, amount_col = st.columns(4)
    price_col.metric("最新价", f"{quote.last_price:,.2f}")
    change_col.metric("涨跌幅", f"{quote.change_pct:+.2f}%", delta=f"{quote.change:+.2f}")
    volume_col.metric("成交量", f"{quote.volume:,.0f}")
    amount_col.metric("成交额", f"{quote.amount:,.0f}")

    open_col, high_col, low_col, prev_col = st.columns(4)
    open_col.metric("今开", f"{quote.open_price:,.2f}")
    high_col.metric("最高", f"{quote.high_price:,.2f}")
    low_col.metric("最低", f"{quote.low_price:,.2f}")
    prev_col.metric("昨收", f"{quote.prev_close:,.2f}")

    st.caption(
        f"数据状态：{quote.data_status}　·　数据更新时间：{quote.updated_at}"
        f"　·　数据来源：{quote.data_source}　·　交易状态：{quote.trading_status}"
    )


def _render_terminal_price_history(history) -> None:
    st.markdown("### K 线历史（收盘价）")
    if history.unavailable_reason or not history.dates:
        st.info(
            f"{terminal.NOT_AVAILABLE_TEXT} — {history.unavailable_reason or '没有可用的历史行情。'}",
            icon="ℹ️",
        )
        return
    st.line_chart({"收盘价": list(history.closes)})
    st.caption(
        f"共 {history.bar_count} 个交易日　·　{history.dates[0]} 至 {history.dates[-1]}"
        f"　·　数据来源：{history.data_source}"
    )


def _render_terminal_technicals(readings) -> None:
    st.markdown("### 技术面")
    for reading in readings:
        if not reading.available:
            st.write(f"**{reading.name}**　{reading.plain_reading}　—　{reading.explanation}")
            continue
        st.write(f"**{reading.name}**　**{reading.plain_reading}**　—　{reading.explanation}")
        st.caption(reading.detail)


def _render_terminal_fundamentals(rows) -> None:
    st.markdown("### 基本面")
    st.table({
        "指标": [row.label for row in rows],
        "数值": [row.value for row in rows],
        "说明": [row.reason or "" for row in rows],
    })


def _render_terminal_news(news, unavailable_reason) -> None:
    st.markdown("### 新闻 / 公告")
    if not news:
        st.info(unavailable_reason or terminal.NOT_AVAILABLE_TEXT, icon="ℹ️")
        return
    st.caption("以下为新闻**事实**原文摘要；AI 的解读单独显示在下方，两者不混同。")
    for item in news:
        st.markdown(f"**{item.title}**")
        st.caption(f"{item.published_at}　·　{item.source}")
        st.write(item.summary)


def _render_terminal_ai(analysis) -> None:
    if analysis.narrative_warning:
        st.error(f"**{analysis.narrative_origin}** — {analysis.narrative_warning}")
    st.markdown("### AI 总结")
    st.write(analysis.summary)
    st.caption(f"数据可信度：{analysis.data_confidence_band}　·　生成时间：{analysis.generated_at}")

    st.markdown("### 风险")
    st.write(analysis.risk)

    bull_col, bear_col = st.columns(2)
    with bull_col:
        st.markdown("### 看多因素")
        st.success(analysis.bull_case)
    with bear_col:
        st.markdown("### 看空因素")
        st.warning(analysis.bear_case)
    st.caption("看多与看空同时呈现，本系统不产生单一买入/卖出结论。")


mode = st.sidebar.radio("模式", ["Terminal", "Research"], index=0)

if mode == "Terminal":
    st.title("📈 AI Quant Terminal")
    st.info(terminal.DISCLAIMER, icon="ℹ️")

    source_label = st.radio(
        "数据源", ["实时行情", "演示数据 (DEMO)"], index=0, horizontal=True,
        key="terminal_source",
        help="实时行情来自公开行情接口；演示数据是固定的示例数据集。两者不会混合显示。",
    )
    quote_source = (terminal.QUOTE_SOURCE_REAL if source_label == "实时行情"
                    else terminal.QUOTE_SOURCE_DEMO)

    options = terminal.list_stocks(quote_source)
    labels = {o["symbol"]: f"{o['symbol']} — {o['display_name']}" for o in options}
    query = st.text_input(
        "搜索股票（代码或名称，实时模式下可直接输入 6 位代码）", key="terminal_search"
    )
    if query.strip():
        matches = terminal.search_stocks(query, quote_source)
        if matches:
            labels = {m["symbol"]: f"{m['symbol']} — {m['display_name']}" for m in matches}
        else:
            st.warning(f"没有找到匹配「{query}」的股票，已显示全部可选标的。", icon="⚠️")

    selected_symbol = st.selectbox(
        "选择股票", options=list(labels.keys()), format_func=lambda s: labels[s],
        key="terminal_symbol",
    )

    try:
        stock = terminal.get_stock_view(selected_symbol, quote_source)
    except terminal.TerminalError as e:
        st.error(f"{terminal.NOT_AVAILABLE_TEXT} — {e}")
        stock = None

    if stock is not None:
        _render_terminal_quote(stock.quote)
        st.markdown("---")

        ai_state_key = f"terminal_ai_{selected_symbol}"
        if st.button("🧠 生成 AI 分析", key="terminal_generate_ai"):
            with st.spinner("正在分析…"):
                try:
                    st.session_state[ai_state_key] = terminal.get_ai_analysis(selected_symbol)
                except terminal.TerminalError as e:
                    st.error(f"AI 分析未能生成：{e}")
        if ai_state_key in st.session_state:
            _render_terminal_ai(st.session_state[ai_state_key])
        else:
            st.caption("点击上方按钮生成 AI 总结、风险与看多/看空分析。")

        st.markdown("---")
        _render_terminal_price_history(stock.price_history)
        st.markdown("---")
        _render_terminal_technicals(stock.technicals)
        st.markdown("---")
        _render_terminal_fundamentals(stock.fundamentals)
        st.markdown("---")
        _render_terminal_news(stock.news, stock.news_unavailable_reason)
        st.markdown("---")
        st.caption(stock.disclaimer)

else:
    st.title("📊 Research Workbench")
    st.caption(
        "Historical Quantitative Research / Backtest Analysis — **Research & Backtest ONLY**. "
        "No broker connection, no order execution, no live trading, no automatic buy/sell."
    )
    st.info(
        "Historical backtest results are research outputs and do not guarantee future "
        "performance. This tool does not provide investment advice or automatic trading signals.",
        icon="ℹ️",
    )

    page = st.sidebar.radio(
        "Navigate", ["New Research Run", "Research Run History", "AI Research Analyst"]
    )

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

    elif page == "AI Research Analyst":
        st.header("AI Research Analyst")
        st.caption(
            "Evidence-grounded research synthesis — every fact and number traces to a cited "
            "Evidence item. Bull Case and Bear Case are both mandatory; this system produces no "
            "single buy/sell verdict."
        )

        provider_status = analyst.get_llm_provider_status()
        if provider_status.status == analyst.LLM_AVAILABLE_STATUS:
            st.success(f"**{provider_status.status}** — {provider_status.message}")
        else:
            st.warning(f"**{provider_status.status}** — {provider_status.message}", icon="⚠️")
        with st.expander("LLM credential pre-flight (informational — no key is ever displayed)"):
            st.json(list(provider_status.credential_reports))

        symbols = analyst.get_analyst_symbols()
        symbol_map = {s["symbol"]: f"{s['symbol']} — {s['display_name']}" for s in symbols}
        analyst_as_of_range = app.get_available_as_of_range()
        a_min = date.fromisoformat(analyst_as_of_range["min_as_of"])
        a_max = date.fromisoformat(analyst_as_of_range["max_as_of"])

        sel_col, date_col = st.columns(2)
        with sel_col:
            analyst_symbol = st.selectbox(
                "Symbol", options=list(symbol_map.keys()),
                format_func=lambda s: symbol_map[s], key="analyst_symbol",
            )
        with date_col:
            analyst_as_of = st.date_input(
                "As-of (PIT cutoff for the ENTIRE report)", value=a_max,
                min_value=a_min, max_value=a_max, key="analyst_as_of",
            )

        try:
            preview_bundle = analyst.get_evidence_bundle_view(analyst_symbol, analyst_as_of)
            _render_evidence_bundle(preview_bundle)
        except analyst.ResearchAnalystError as e:
            st.error(str(e))
            preview_bundle = None

        real_available = provider_status.status == analyst.LLM_AVAILABLE_STATUS
        selectable = list(provider_status.available_provider_ids) or list(
            provider_status.implemented_provider_ids
        )
        selected_provider = st.selectbox(
            "LLM provider", options=selectable,
            index=(selectable.index(provider_status.selected_provider_id)
                   if provider_status.selected_provider_id in selectable else 0),
            format_func=lambda pid: (
                f"{pid}" + ("" if pid in provider_status.available_provider_ids
                            else "  (no credential configured)")
            ),
            key="analyst_provider",
            help="Both providers implement the same interface; switching vendors changes nothing "
                 "upstream of the provider call.",
        )
        narrative_source = st.radio(
            "Narrative source",
            options=["Real LLM provider", "Labelled SYNTHETIC placeholder"],
            index=0 if real_available else 1,
            key="analyst_narrative_source",
            help=(
                "The real provider makes a billable API call and produces genuine analysis of the "
                "Evidence Bundle. The synthetic placeholder calls no API and is not analysis — it "
                "renders the pipeline with prose that says so in every section."
            ),
        )
        use_real = narrative_source == "Real LLM provider"
        if use_real and selected_provider not in provider_status.available_provider_ids:
            st.warning(
                f"No credential is configured for `{selected_provider}` — generation will fail "
                "closed rather than fall back to another vendor or to a synthetic narrative.",
                icon="⚠️",
            )

        if st.button("🧠 Generate AI Research Report", key="analyst_generate"):
            with st.spinner("Generating…" if use_real else "Rendering…"):
                try:
                    view = analyst.generate_analyst_report(
                        analyst_symbol, analyst_as_of,
                        allow_synthetic_narrative=not use_real, use_real_provider=use_real,
                        provider_id=selected_provider if use_real else None,
                    )
                    st.session_state["last_analyst_report_id"] = view.report_id
                    st.success(f"Report generated and persisted: `{view.report_id}`")
                except analyst.ResearchAnalystError as e:
                    st.error(f"FAIL CLOSED — {e}")

        st.markdown("---")
        st.subheader("Persisted reports")
        persisted = analyst.list_analyst_reports()
        if not persisted:
            st.write("_No persisted AI research reports yet._")
        else:
            report_options = {
                r.report_id: f"{r.symbol} @ {r.as_of} ({r.narrative_origin}, {r.generated_at})"
                for r in persisted
            }
            default_id = st.session_state.get("last_analyst_report_id")
            ids = list(report_options.keys())
            selected_report = st.selectbox(
                "Select a report", options=ids,
                index=ids.index(default_id) if default_id in ids else 0,
                format_func=lambda k: report_options[k], key="analyst_report_select",
            )
            if selected_report:
                st.markdown("---")
                try:
                    _render_analyst_report(analyst.get_analyst_report(selected_report))
                except analyst.ResearchAnalystError as e:
                    st.error(str(e))

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

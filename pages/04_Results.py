"""Page 4 — Results.

Displays:
  A. Summary margin bar chart (Plotly)
  B. Preload waterfall chart (Plotly)
  C. Step-by-step calculation accordion (LaTeX formulas)
  D. Warnings panel
  E. Load case comparison table
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from boltsizer.ui.session_state import init_session_state, mark_page_complete, render_sidebar_progress
from boltsizer.ui.components.margin_bar import make_margin_bar_chart
from boltsizer.ui.components.force_waterfall import make_preload_waterfall
from boltsizer.ui.components.calc_step_card import render_calc_steps

st.set_page_config(page_title="Results — BoltSizer", page_icon="📊", layout="wide")
init_session_state()
render_sidebar_progress()

st.title("📊 Step 4: Results")

results = st.session_state.get("analysis_results")

if results is None:
    st.warning("⚠ No analysis results yet. Please complete the inputs and run the analysis on the Loading page.")
    st.page_link("pages/03_Loading.py", label="Go to Loading page →", icon="⚡")
    st.stop()

mark_page_complete("Results", True)


def _status_icon(s: str) -> str:
    return {"PASS": "✅", "WARNING": "⚠️", "FAIL": "❌"}.get(s, s)


def render_case(case_result, standard: str) -> None:
    """Render the full results view for a single load case."""
    preload = case_result.preload
    stiffness = case_result.stiffness
    load_dist = case_result.load_dist
    margins = case_result.margins
    warnings = case_result.warnings
    calc_steps = case_result.calc_steps

    # --- Status banner ---
    worst_ms = min((m.value for m in margins if m.value != float("inf")), default=float("inf"))
    num_fail = sum(1 for m in margins if m.status == "FAIL")
    num_warn = sum(1 for m in margins if m.status == "WARNING")
    num_pass = sum(1 for m in margins if m.status == "PASS")

    if num_fail > 0:
        st.error(f"❌ {num_fail} check(s) FAILED | Worst MS = {worst_ms:.3f}")
    elif num_warn > 0:
        st.warning(f"⚠ {num_warn} check(s) in WARNING zone | Worst MS = {worst_ms:.3f}")
    else:
        st.success(f"✅ All {num_pass} checks PASS | Worst MS = {worst_ms:.3f}")

    st.caption(
        f"Standard: **{standard}** | "
        f"Critical bolt: **#{load_dist.critical_bolt_index + 1}** "
        f"(F_axial = {load_dist.F_total_axial:,.0f} N, "
        f"V_shear = {load_dist.V_shear_per_bolt:,.0f} N)"
    )

    # --- Charts ---
    col_bar, col_wf = st.columns([3, 2], gap="large")
    with col_bar:
        st.markdown("#### Margin of Safety Summary")
        fig_bar = make_margin_bar_chart(margins, title="")
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_wf:
        st.markdown("#### Preload Budget")
        fig_wf = make_preload_waterfall(
            preload, stiffness,
            F_ext=load_dist.F_total_axial,
            title="",
        )
        st.plotly_chart(fig_wf, use_container_width=True)

    # --- Margin detail table ---
    st.markdown("#### Margin Detail")
    rows = []
    for m in margins:
        v_str = "∞" if m.value == float("inf") else f"{m.value:.3f}"
        rows.append({
            "Check": ("★ " if m.binding else "  ") + m.check_name,
            "Status": _status_icon(m.status),
            "MS": v_str,
            "Allowable": f"{m.allowable:.2f} {m.unit}",
            "Applied": f"{m.applied:.2f} {m.unit}",
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # --- Key numbers ---
    st.markdown("#### Key Results")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Min Preload F_V_min", f"{preload.F_preload_min:,.0f} N")
    k2.metric("Max Bolt Load", f"{case_result.bolt_load_max:,.0f} N")
    k3.metric("Force Ratio φ_n", f"{stiffness.phi_n:.4f}")
    k4.metric("Min Clamping Force", f"{case_result.F_clamp_min:,.0f} N")

    # --- Warnings ---
    if warnings:
        st.markdown("#### Warnings")
        for w in warnings:
            if "⚠" in w:
                st.warning(w)
            else:
                st.info(w)

    # --- Step-by-step accordion ---
    st.divider()
    with st.expander("🔍 Show Full Calculation Chain", expanded=False):
        render_calc_steps(calc_steps)

    # --- Per-check explanations ---
    st.divider()
    st.markdown("#### Failure Mode Explanations")
    for m in margins:
        v_str = "∞" if m.value == float("inf") else f"{m.value:.3f}"
        icon = _status_icon(m.status)
        with st.expander(f"{icon} {m.check_name} — MS = {v_str}"):
            if m.formula_latex:
                st.latex(m.formula_latex)
            st.markdown(m.explanation)
            c1, c2, c3 = st.columns(3)
            c1.metric("Allowable", f"{m.allowable:.2f} {m.unit}")
            c2.metric("Applied", f"{m.applied:.2f} {m.unit}")
            c3.metric("Margin of Safety", v_str)


# ---------------------------------------------------------------------------
# Load case tabs
# ---------------------------------------------------------------------------
case_names = [cr.case_name for cr in results.case_results]

if len(case_names) > 1:
    # Multiple cases: use tabs + summary comparison table
    st.subheader("Load Case Comparison")
    cmp_rows = []
    for cr in results.case_results:
        worst_ms = min((m.value for m in cr.margins if m.value != float("inf")), default=float("inf"))
        binding = next((m for m in cr.margins if m.binding), None)
        cmp_rows.append({
            "Case": cr.case_name,
            "Worst MS": f"{worst_ms:.3f}",
            "Binding Check": binding.check_name if binding else "—",
            "Status": _status_icon("FAIL" if worst_ms < 0 else ("WARNING" if worst_ms < 0.25 else "PASS")),
        })
    st.dataframe(pd.DataFrame(cmp_rows), use_container_width=True, hide_index=True)
    st.divider()

    tabs = st.tabs(case_names)
    for tab_ctx, cr in zip(tabs, results.case_results):
        with tab_ctx:
            render_case(cr, results.standard)
else:
    render_case(results.case_results[0], results.standard)

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
st.divider()
col_back, col_fwd = st.columns(2)
with col_back:
    st.page_link("pages/03_Loading.py", label="← Back: Loading", icon="⚡")
with col_fwd:
    st.page_link("pages/05_Report.py", label="Next: Report →", icon="📄")

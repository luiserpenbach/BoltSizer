"""Page 5 — Report.

Generates a PDF calculation report with:
  - Project metadata
  - Input summary
  - Full margin table
  - Calculation chain
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from boltsizer.ui.session_state import init_session_state, mark_page_complete, render_sidebar_progress

st.set_page_config(page_title="Report — BoltSizer", page_icon="📄", layout="wide")
init_session_state()
render_sidebar_progress()

st.title("📄 Step 5: Export Report")

results = st.session_state.get("analysis_results")
bolt_cfg = st.session_state.get("bolt_config", {})
joint_cfg = st.session_state.get("joint_config", {})

# ---------------------------------------------------------------------------
# Report metadata
# ---------------------------------------------------------------------------
st.subheader("Report Header")
meta = st.session_state.get("report_meta", {})

c1, c2, c3 = st.columns(3)
with c1:
    meta["project_name"] = st.text_input(
        "Project name", value=meta.get("project_name", ""), placeholder="e.g. Engine Flange Interface"
    )
with c2:
    meta["revision"] = st.text_input(
        "Revision", value=meta.get("revision", "A"), max_chars=4
    )
with c3:
    meta["engineer_name"] = st.text_input(
        "Engineer", value=meta.get("engineer_name", ""), placeholder="Your name"
    )

st.session_state["report_meta"] = meta

# ---------------------------------------------------------------------------
# Generate button
# ---------------------------------------------------------------------------
st.divider()

if results is None:
    st.warning("⚠ No analysis results yet. Please run the analysis on the Loading page first.")
    st.page_link("pages/03_Loading.py", label="Go to Loading page →", icon="⚡")
    st.stop()

if st.button("📥 Generate PDF Report", type="primary", use_container_width=True):
    with st.spinner("Generating PDF report…"):
        try:
            from boltsizer.export.pdf_report import generate_pdf_report
            pdf_bytes = generate_pdf_report(
                results=results,
                bolt_cfg=bolt_cfg,
                joint_cfg=joint_cfg,
                report_meta=meta,
            )
            st.success("✅ Report generated successfully!")
            st.download_button(
                label="⬇ Download PDF",
                data=pdf_bytes,
                file_name=f"BoltSizer_{meta.get('project_name', 'Report').replace(' ', '_')}_Rev{meta.get('revision', 'A')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
            mark_page_complete("Report", True)
        except Exception as e:
            st.error(f"PDF generation error: {e}")
            import traceback
            st.code(traceback.format_exc())

# ---------------------------------------------------------------------------
# JSON save/load
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Save / Load Case")

col_save, col_load = st.columns(2)

with col_save:
    st.markdown("**Save current case as JSON**")
    if st.button("💾 Export JSON", use_container_width=True):
        try:
            import json
            import datetime
            case_data = {
                "metadata": {
                    **meta,
                    "date": datetime.date.today().isoformat(),
                    "standard": st.session_state.get("standard", "VDI"),
                },
                "bolt_config": bolt_cfg,
                "joint_config": joint_cfg,
                "load_cases": st.session_state.get("load_cases", []),
            }
            json_str = json.dumps(case_data, indent=2, default=str)
            st.download_button(
                label="⬇ Download JSON",
                data=json_str.encode(),
                file_name=f"BoltSizer_{meta.get('project_name', 'Case').replace(' ', '_')}.json",
                mime="application/json",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"JSON export error: {e}")

with col_load:
    st.markdown("**Load case from JSON**")
    uploaded = st.file_uploader("Upload JSON", type="json", label_visibility="collapsed")
    if uploaded is not None:
        try:
            import json
            data = json.loads(uploaded.read())
            if "bolt_config" in data:
                st.session_state["bolt_config"] = data["bolt_config"]
            if "joint_config" in data:
                st.session_state["joint_config"] = data["joint_config"]
            if "load_cases" in data:
                st.session_state["load_cases"] = data["load_cases"]
            if "metadata" in data:
                st.session_state["report_meta"] = data["metadata"]
                if "standard" in data["metadata"]:
                    st.session_state["standard"] = data["metadata"]["standard"]
            st.success("✅ Case loaded. Please re-run the analysis.")
            st.session_state["analysis_results"] = None
        except Exception as e:
            st.error(f"JSON load error: {e}")

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
st.divider()
st.page_link("pages/04_Results.py", label="← Back: Results", icon="📊")

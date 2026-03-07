"""BoltSizer — Structural Flange Bolt Sizing Tool.

Streamlit multi-page application entry point.

Usage:
    streamlit run app.py

Implements VDI 2230 (Part 1, 2014) and ECSS-E-HB-32-23A methodologies.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from boltsizer.ui.session_state import init_session_state, render_sidebar_progress

st.set_page_config(
    page_title="BoltSizer — Structural Bolt Sizing",
    page_icon="🔩",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()
render_sidebar_progress()

# ---------------------------------------------------------------------------
# Home / landing page
# ---------------------------------------------------------------------------
st.title("🔩 BoltSizer")
st.subheader("Structural Flange Bolt Sizing Tool")
st.markdown(
    """
    BoltSizer implements **VDI 2230 Part 1 (2014)** and **ECSS-E-HB-32-23A** bolt sizing
    methodologies with full calculation transparency — showing the complete calculation chain,
    annotating the binding constraint, and explaining each failure mode.

    ---
    ### Workflow
    | Step | Page | Description |
    |------|------|-------------|
    | 1 | 🔩 Bolt Selection | Select bolt size, grade, coating, and tightening parameters |
    | 2 | 📐 Joint Geometry | Define bolt circle, clamped stack layers, and interface friction |
    | 3 | ⚡ Loading | Enter load cases (axial, bending, shear) |
    | 4 | 📊 Results | Review margins of safety, waterfall chart, and calculation chain |
    | 5 | 📄 Report | Export PDF calculation note and save/load JSON cases |

    ---
    ### Failure Modes Checked
    - **Yield at assembly** — 90% proof load utilisation
    - **Yield under combined load** — Von Mises (axial + torsion)
    - **Joint separation** — clamping force vs. external opening force
    - **Interface slip** — friction capacity vs. shear
    - **Bolt shear** — Tresca shear capacity
    - **Bearing** — plate bearing stress
    - **Fatigue** — infinite-life check (bolt load amplitude vs. material limit)

    ---
    ### Standards & References
    - VDI 2230 Part 1 (2014)
    - ECSS-E-HB-32-23A (2010)
    - ISO 898-1:2013

    > **Out of scope (v1):** Gasket flanges (ASME VIII / EN 1591), eccentric bolt groups,
    > thermal loading, fatigue life calculation, 3D visualisation.
    """
)

st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("pages/01_Bolt_Selection.py", label="Start: Bolt Selection →", icon="🔩", use_container_width=True)
with col2:
    st.page_link("pages/04_Results.py", label="Jump to Results", icon="📊", use_container_width=True)
with col3:
    st.page_link("pages/05_Report.py", label="Export Report", icon="📄", use_container_width=True)

"""Centralised session state management for BoltSizer Streamlit app.

All mutable state lives here. Calculation modules are pure functions —
they receive data from session state and return results.

Keys:
  bolt_config      – dict of bolt selection inputs
  joint_config     – dict of joint geometry inputs
  load_cases       – list of load case dicts
  analysis_results – AnalysisResults or None
  standard         – "VDI" | "ECSS"
  page_complete    – dict[page_name: bool] for sidebar progress indicators
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import streamlit as st


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------
DEFAULT_BOLT_CONFIG: Dict[str, Any] = {
    "designation": "M12",
    "grade": "ISO 8.8",
    "coating": "Dry (as-machined steel)",
    "tightening_method": "torque_wrench",
    "assembly_torque_Nmm": 85000.0,
    "use_target_preload": False,
    "target_preload_N": 30000.0,
    "num_mating_surfaces": 2,
    "surface_roughness_Rz": 6.3,
}

DEFAULT_JOINT_CONFIG: Dict[str, Any] = {
    "num_bolts": 8,
    "bolt_circle_diameter_mm": 100.0,
    "layers": [
        {"material": "Steel (carbon)", "thickness_mm": 20.0},
        {"material": "Steel (carbon)", "thickness_mm": 20.0},
    ],
    "interface_treatment": "bare metal",
    "friction_coefficient": 0.12,
    "num_friction_interfaces": 1,
    "load_intro_factor_n": 0.5,
    "plate_thickness_mm": 20.0,
    "plate_yield_strength_MPa": 240.0,
}

DEFAULT_LOAD_CASE: Dict[str, Any] = {
    "case_name": "LC1",
    "axial_force_N": 10000.0,
    "bending_moment_Nmm": 0.0,
    "shear_force_N": 5000.0,
    "torsion_Nmm": 0.0,
    "load_plane": "interface",
    "load_factor": 1.0,
}


def init_session_state() -> None:
    """Initialise all session state keys with defaults if not yet set."""
    defaults: Dict[str, Any] = {
        "bolt_config": DEFAULT_BOLT_CONFIG.copy(),
        "joint_config": DEFAULT_JOINT_CONFIG.copy(),
        "load_cases": [DEFAULT_LOAD_CASE.copy()],
        "analysis_results": None,
        "standard": "VDI",
        "page_complete": {
            "Bolt Selection": False,
            "Joint Geometry": False,
            "Loading": False,
            "Results": False,
            "Report": False,
        },
        "report_meta": {
            "project_name": "",
            "revision": "A",
            "engineer_name": "",
        },
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get(key: str, default: Any = None) -> Any:
    """Get a session state value."""
    return st.session_state.get(key, default)


def set_value(key: str, value: Any) -> None:
    """Set a session state value."""
    st.session_state[key] = value


def mark_page_complete(page_name: str, complete: bool = True) -> None:
    """Mark a page as complete/incomplete in the progress checklist."""
    if "page_complete" in st.session_state:
        st.session_state["page_complete"][page_name] = complete


def render_sidebar_progress() -> None:
    """Render the progress checklist in the sidebar."""
    with st.sidebar:
        st.markdown("## BoltSizer")
        st.markdown("*Structural Flange Bolt Sizing*")
        st.divider()
        st.markdown("### Progress")
        pages = [
            ("Bolt Selection", "pages/01_Bolt_Selection"),
            ("Joint Geometry", "pages/02_Joint_Geometry"),
            ("Loading", "pages/03_Loading"),
            ("Results", "pages/04_Results"),
            ("Report", "pages/05_Report"),
        ]
        page_complete = st.session_state.get("page_complete", {})
        for page_name, _ in pages:
            done = page_complete.get(page_name, False)
            icon = "✅" if done else "⬜"
            st.markdown(f"{icon} {page_name}")

        st.divider()
        standard = st.selectbox(
            "Standard",
            options=["VDI", "ECSS"],
            index=0 if st.session_state.get("standard", "VDI") == "VDI" else 1,
            help=(
                "VDI: VDI 2230 Part 1 (2014) conventions.\n"
                "ECSS: ECSS-E-HB-32-23A — more conservative minimum preload for separation/slip."
            ),
            key="sidebar_standard",
        )
        st.session_state["standard"] = standard

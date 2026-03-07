"""Expandable calculation step card component for Streamlit."""
from __future__ import annotations
from typing import Any, Dict, List
import streamlit as st


def render_calc_steps(calc_steps: List[Dict[str, Any]]) -> None:
    """Render an expandable accordion of calculation steps.

    Each step dict should have:
        step:         Step title string
        formula_latex: LaTeX formula string
        substitution: Variable substitution string
        result:       Computed result string
        explanation:  Plain-English explanation sentence

    Args:
        calc_steps: List of step dicts.
    """
    st.markdown("#### Step-by-Step Calculation")
    for i, step in enumerate(calc_steps, 1):
        with st.expander(f"Step {i}: {step.get('step', '')}"):
            col1, col2 = st.columns([2, 3])
            with col1:
                st.markdown("**Formula:**")
                formula = step.get("formula_latex", "")
                if formula:
                    st.latex(formula)
                st.markdown("**Substitution:**")
                st.code(step.get("substitution", ""), language=None)
            with col2:
                st.markdown("**Result:**")
                st.info(step.get("result", ""))
                st.markdown("**Why this matters:**")
                st.caption(step.get("explanation", ""))

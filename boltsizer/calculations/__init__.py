"""Calculation modules for BoltSizer.

All functions are pure (no side-effects, no global state).
Inputs in SI units (N, mm, MPa); outputs in SI units.
"""
from .preload import calculate_preload
from .joint_stiffness import calculate_joint_stiffness
from .load_distribution import calculate_load_distribution
from .failure_modes import calculate_all_margins
from .vdi2230 import run_vdi2230_analysis

__all__ = [
    "calculate_preload",
    "calculate_joint_stiffness",
    "calculate_load_distribution",
    "calculate_all_margins",
    "run_vdi2230_analysis",
]

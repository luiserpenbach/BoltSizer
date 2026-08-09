"""Nut factor (K-factor) and tightening scatter tables.

Sources:
  NASA-STD-5020B / Bickford — K-factor (nut factor) guidance.  Note the
    K-factor torque relation is NOT part of VDI 2230; VDI uses the full
    thread-geometry torque decomposition.  The K shortcut is retained here
    because it is standard aerospace practice.
  VDI 2230 Part 1 (2014) Table A8 — tightening factor α_A guide values.

The nut/K-factor K relates applied torque to bolt preload:
    F_M = M_A / (K · d)
where d is the nominal bolt diameter [mm], M_A is the assembly torque [N·mm],
and F_M is the resulting NOMINAL preload [N].

Tightening scatter factor α_A = F_M_max / F_M_min.  The preload module
applies it symmetrically about the nominal:
    ε = (α_A − 1) / (α_A + 1)
    F_M_max = F_M_nom · (1 + ε),   F_M_min = F_M_nom · (1 − ε)
so that F_M_max / F_M_min = α_A exactly.
"""
from __future__ import annotations
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# K-factor table
# Key: condition description
# Value: (K_nom, K_min, K_max, description)
# ---------------------------------------------------------------------------
NUT_FACTOR_TABLE: Dict[str, tuple] = {
    #  condition                  K_nom  K_min  K_max   notes
    "Dry (as-machined steel)":  (0.20,  0.17,  0.23,  "Unlubricated clean steel"),
    "Lightly oiled":            (0.18,  0.16,  0.21,  "Light machine oil film"),
    "Cadmium plated":           (0.16,  0.14,  0.18,  "Cd or Cd-Ti plating"),
    "Zinc plated":              (0.18,  0.15,  0.21,  "Electroplated zinc"),
    "Hot-dip galvanised":       (0.19,  0.16,  0.23,  "Hot-dip zinc"),
    "MoS₂ dry film":            (0.13,  0.11,  0.15,  "Molybdenum disulphide"),
    "PTFE thread insert":       (0.12,  0.10,  0.14,  "PTFE-coated/insert (e.g. Heli-Coil)"),
    "Silver-plated":            (0.14,  0.12,  0.16,  "Silver plating (cryogenic safe)"),
    "Moly-powder (wet)":        (0.11,  0.09,  0.13,  "MoS₂ wet compound"),
    "Copper anti-seize":        (0.17,  0.14,  0.20,  "Copper-based anti-seize"),
    "Nickel-based anti-seize":  (0.18,  0.15,  0.21,  "Nickel-based anti-seize"),
    "User-defined":             (0.20,  0.20,  0.20,  "User-specified value"),
}

# ---------------------------------------------------------------------------
# Tightening method scatter factors (VDI 2230 Part 1 (2014) Table A8
# guide values; where the table gives a range, a representative value is
# used — conservative end for uncontrolled methods)
# Key: tightening method
# Value: (alpha_A, description)
# alpha_A = F_M_max / F_M_min
# ---------------------------------------------------------------------------
TIGHTENING_SCATTER: Dict[str, tuple] = {
    #  method                    α_A   description
    "torque_wrench":            (1.60, "Torque wrench (VDI range 1.4–1.6)"),
    "torque_wrench_precise":    (1.40, "Torque wrench, calibrated (VDI 1.4)"),
    "torque_angle":             (1.20, "Torque + angle control (VDI 1.2–1.4)"),
    "hydraulic_tensioning":     (1.20, "Hydraulic bolt tensioner (VDI 1.1–1.2)"),
    "ultrasonic":               (1.10, "Ultrasonic / elongation measurement"),
    "hand_tight":               (2.50, "Hand tight only (estimate)"),
    "impact_wrench":            (2.50, "Impact wrench (VDI range 2.5–4)"),
}

# Human-readable method names for UI display
TIGHTENING_METHOD_LABELS: Dict[str, str] = {
    "torque_wrench":         "Torque wrench (standard)",
    "torque_wrench_precise": "Torque wrench (calibrated)",
    "torque_angle":          "Torque + angle",
    "hydraulic_tensioning":  "Hydraulic tensioner",
    "ultrasonic":            "Ultrasonic elongation",
    "hand_tight":            "Hand tight",
    "impact_wrench":         "Impact wrench",
}


def get_nut_factor(condition: str) -> float:
    """Return the nominal K-factor for the given surface/coating condition.

    Args:
        condition: Key from NUT_FACTOR_TABLE.

    Returns:
        Nominal K value.
    """
    if condition not in NUT_FACTOR_TABLE:
        return 0.20  # Default to dry
    return NUT_FACTOR_TABLE[condition][0]


def get_nut_factor_range(condition: str) -> tuple:
    """Return (K_nom, K_min, K_max) for the given surface/coating condition.

    Used to bracket the achievable preload: low friction (K_min) gives the
    highest preload at a given torque, high friction (K_max) the lowest.

    Args:
        condition: Key from NUT_FACTOR_TABLE.

    Returns:
        Tuple (K_nom, K_min, K_max); defaults to (0.20, 0.17, 0.23) if the
        condition is unknown.
    """
    if condition not in NUT_FACTOR_TABLE:
        return (0.20, 0.17, 0.23)
    k_nom, k_min, k_max, _ = NUT_FACTOR_TABLE[condition]
    return (k_nom, k_min, k_max)


def get_scatter_factor(tightening_method: str) -> float:
    """Return the tightening scatter factor α_A for the given method.

    Args:
        tightening_method: Key from TIGHTENING_SCATTER.

    Returns:
        α_A value.
    """
    if tightening_method not in TIGHTENING_SCATTER:
        return 1.60  # Conservative default
    return TIGHTENING_SCATTER[tightening_method][0]

"""ECSS-E-HB-32-23A margin and factor definitions.

Reference: ECSS-E-HB-32-23A "Threaded fastener design manual" (2010).

Key differences vs VDI 2230:
  1. Minimum preload for separation/slip uses F_M_min (before embedding) — conservative.
  2. Yield margin requires FoS = 1.1 on design limit load (absorbed into load_factor).
  3. Torque-to-yield tightening is prohibited for space hardware.
  4. Self-loosening risk must be formally assessed with locking device recommendation.
  5. Margin table format specifies columns: Check | Allowable | Applied | MS.
"""
from __future__ import annotations
from typing import Dict

# ---------------------------------------------------------------------------
# ECSS typical load factors (Table 3-1, ECSS-E-ST-32C)
# These are guidelines; actual factors from project structural verification plan.
# ---------------------------------------------------------------------------
ECSS_LOAD_FACTORS: Dict[str, float] = {
    "Yield (DLL → DUL)":    1.1,   # Design limit to ultimate load factor
    "Ultimate (DLL → DUL)": 1.5,   # Applied to DLL to get DUL for fracture
    "Fatigue":               1.0,   # Applied loads (design loads)
    "Separation/Slip":       1.0,   # Joint loads at design limit
}


def ecss_minimum_preload(
    F_M_min: float,
    F_Z: float,
) -> float:
    """Return the ECSS minimum preload for separation/slip checks.

    ECSS-E-HB-32-23A §8.3.2: minimum preload is defined as F_M_min
    WITHOUT the embedding relaxation subtracted.  This is the conservative
    (lower) definition compared to VDI 2230 which subtracts F_Z.

    Args:
        F_M_min: Minimum scatter preload [N] (after tightening scatter only).
        F_Z: Embedding relaxation force [N].

    Returns:
        ECSS minimum preload [N] = F_M_min (without F_Z).
    """
    return F_M_min  # Deliberately not subtracting F_Z


def ecss_yield_margin_factor() -> float:
    """Return ECSS yield factor of safety for yield margin calculation.

    ECSS-E-ST-32C §4.3: Factor 1.1 on design limit load for yield check.
    When load_factor already includes this (FoS baked into applied load),
    the margin allowable is just σ_y with no additional factor.

    Returns:
        Factor of safety value = 1.1.
    """
    return 1.1

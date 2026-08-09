"""ECSS-E-HB-32-23A margin and factor definitions.

Reference: ECSS-E-HB-32-23A "Threaded fastener design manual" (2010),
ECSS-E-ST-32-10C "Structural factors of safety for spaceflight hardware".

Key points of the ECSS convention as implemented:
  1. The minimum preload for separation/slip includes ALL preload losses
     (tightening scatter, embedding, thermal).  Ignoring a loss term
     overstates the separation margin.
  2. Yield and ultimate margins carry the ECSS factors of safety
     (baseline FOSY = 1.1, FOSU = 1.25 for metallic hardware verified by
     analysis; override with the project structural verification plan).
  3. A separation (gapping) factor of safety (baseline 1.2) is applied to
     the opening demand.
  4. Torque-to-yield tightening is prohibited for space hardware
     (utilisation warning raised at >90% of proof).
  5. Self-loosening risk must be formally assessed with locking device
     recommendation.
"""
from __future__ import annotations
from typing import Dict

# ---------------------------------------------------------------------------
# ECSS baseline factors of safety (ECSS-E-ST-32-10C guidance values).
# Actual factors come from the project structural verification plan —
# these are defaults applied when the ECSS convention is selected and the
# user does not override them.
# ---------------------------------------------------------------------------
ECSS_DEFAULT_FOS: Dict[str, float] = {
    "yield":      1.1,
    "ultimate":   1.25,
    "separation": 1.2,
    "slip":       1.0,   # set per project (often ≥ 1.1 for friction-critical)
}

# VDI convention: margins on limit load; project factors enter via the
# load_factor on each load case.
VDI_DEFAULT_FOS: Dict[str, float] = {
    "yield":      1.0,
    "ultimate":   1.0,
    "separation": 1.0,
    "slip":       1.0,
}


def get_default_fos(standard: str) -> Dict[str, float]:
    """Return the default factor-of-safety set for the given convention."""
    return dict(ECSS_DEFAULT_FOS if standard == "ECSS" else VDI_DEFAULT_FOS)

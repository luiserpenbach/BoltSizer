"""Preload calculation module — VDI 2230 Part 1 (2014) §4 and §5.4.

Sign convention: forces are positive in tension (bolt stretching direction).
Units: N (force), mm (length), MPa (stress), N·mm (torque).

Reference equations:
  VDI 2230 (2014) Eq. (5.1):  F_M = M_A / (K · d)
  VDI 2230 (2014) Table A5:   α_A tightening scatter factors
  VDI 2230 (2014) Table 5.4:  f_Z embedding relaxation
"""
from __future__ import annotations
import math
from typing import Optional
from boltsizer.models.bolt import Bolt
from boltsizer.models.joint import BoltCircle
from boltsizer.models.results import PreloadResult
from boltsizer.standards.nut_factors import get_scatter_factor

# ---------------------------------------------------------------------------
# LaTeX formula strings (kept adjacent to calculations for traceability)
# ---------------------------------------------------------------------------
FORMULA_TORQUE_TO_PRELOAD = r"F_M = \frac{M_A}{K \cdot d}"
FORMULA_SCATTER_MIN = r"F_{M,\min} = \frac{F_{M,\max}}{\alpha_A}"
FORMULA_EMBEDDING = r"F_Z = \frac{f_Z \cdot E_S \cdot A_S}{l_K}"
FORMULA_NET_PRELOAD_MIN = r"F_{V,\min} = F_{M,\min} - F_Z"

# VDI 2230 Table 5.4 — Embedding displacement f_Z [mm]
# Rows: number of mating surfaces (1..5)
# Cols: surface roughness Rz [μm] thresholds: ≤ 4, ≤ 10, ≤ 16, ≤ 40
_EMBEDDING_TABLE: dict = {
    # n_interfaces: {Rz_threshold: f_Z [mm]}
    1: {4: 0.003, 10: 0.005, 16: 0.010, 40: 0.020, 9999: 0.025},
    2: {4: 0.005, 10: 0.010, 16: 0.015, 40: 0.025, 9999: 0.035},
    3: {4: 0.008, 10: 0.015, 16: 0.020, 40: 0.035, 9999: 0.050},
    4: {4: 0.010, 10: 0.020, 16: 0.025, 40: 0.045, 9999: 0.065},
    5: {4: 0.013, 10: 0.025, 16: 0.030, 40: 0.055, 9999: 0.075},
}


def _get_embedding_displacement(num_interfaces: int, rz_um: float) -> float:
    """Look up embedding displacement f_Z [mm] from VDI 2230 Table 5.4.

    VDI 2230 (2014) Table 5.4.

    Args:
        num_interfaces: Number of mating/embedding surfaces (1–5).
        rz_um: Mean surface roughness Rz [μm].

    Returns:
        f_Z in mm.
    """
    n = max(1, min(num_interfaces, 5))
    row = _EMBEDDING_TABLE[n]
    for threshold, f_z in sorted(row.items()):
        if rz_um <= threshold:
            return f_z
    return max(row.values())


def calculate_preload(
    bolt_circle: BoltCircle,
    grip_length: float,
) -> PreloadResult:
    """Calculate bolt preload including scatter and embedding relaxation.

    Steps:
      1. Convert assembly torque to nominal preload (or use direct target).
         VDI 2230 (2014) Eq. (5.1): F_M = M_A / (K · d)
      2. Apply tightening scatter to get min/max preload.
         VDI 2230 (2014) Table A5: F_M_min = F_M_max / α_A
      3. Compute embedding relaxation force.
         VDI 2230 (2014) Table 5.4: F_Z = f_Z · E_S · A_S / l_K
      4. Net minimum preload: F_V_min = F_M_min - F_Z.

    Args:
        bolt_circle: BoltCircle specification including tightening parameters.
        grip_length: Total clamped stack (grip) length l_K [mm].

    Returns:
        PreloadResult with all intermediate values.
    """
    bolt = bolt_circle.bolt
    d = bolt.geometry.nominal_diameter       # [mm]
    K = bolt_circle.nut_factor_K
    A_s = bolt.geometry.stress_area          # [mm²]
    E_S = bolt.material.youngs_modulus       # [MPa]

    # --- Step 1: Nominal preload ---
    if bolt_circle.assembly_torque > 0:
        # VDI 2230 (2014) Eq. (5.1)
        F_M_nominal = bolt_circle.assembly_torque / (K * d)
    else:
        # Direct target preload mode
        F_M_nominal = bolt_circle.target_preload
    F_M_max = F_M_nominal  # Target torque achieves maximum preload

    # --- Step 2: Tightening scatter ---
    # VDI 2230 (2014) Table A5
    alpha_A = get_scatter_factor(bolt_circle.tightening_method)
    F_M_min = F_M_max / alpha_A

    # --- Step 3: Embedding relaxation ---
    # VDI 2230 (2014) Table 5.4
    f_Z = _get_embedding_displacement(
        bolt_circle.num_mating_surfaces,
        bolt_circle.surface_roughness_Rz,
    )
    # Embedding loss force: F_Z = f_Z * E_S * A_S / l_K
    # Derived from δ = F·l/(E·A) → F = δ·E·A/l
    F_Z = (f_Z * E_S * A_s / grip_length) if grip_length > 0 else 0.0

    # --- Step 4: Net minimum preload ---
    F_preload_min = max(0.0, F_M_min - F_Z)
    F_preload_max = F_M_max  # Embedding doesn't increase preload

    return PreloadResult(
        F_M_nominal=F_M_nominal,
        F_M_max=F_M_max,
        F_M_min=F_M_min,
        F_Z=F_Z,
        F_preload_max=F_preload_max,
        F_preload_min=F_preload_min,
        alpha_A=alpha_A,
        f_Z_displacement=f_Z,
    )

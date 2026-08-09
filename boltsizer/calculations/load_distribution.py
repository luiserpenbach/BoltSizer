"""Bolt pattern load distribution — axial + bending + shear + torsion.

Supports circular, rectangular and custom XY bolt patterns.  For every
pattern the loads resolve about the pattern centroid:
  - Axial (membrane): equal share per bolt.
  - Bending: bolt axial force ∝ x-coordinate (moment axis along Y):
        F_B,i = M_B · x_i / Σ x_j²
    (Rigid flange, elastic bolts — the classic bolt-group assumption.
    For a circle this reduces to F_B,i = M·r·cosθ_i / Σ r²cos²θ, i.e.
    F_max = 2M/(n·r).)
  - Shear: equal direct share per bolt.
  - Torsion about the pattern axis: tangential shear ∝ radius:
        V_t,i = M_T · r_i / Σ r_j²
    Combined with the direct share by scalar addition (conservative —
    the direct-shear direction relative to the pattern is not tracked).

Reference:
  Bickford, "An Introduction to the Design and Behavior of Bolted Joints",
  4th ed., §6; ECSS-E-HB-32-23A §8 — bolt group analysis.

Sign convention: tension positive.
"""
from __future__ import annotations
import math
from typing import List, Tuple
from boltsizer.models.joint import BoltCircle, ExternalLoading
from boltsizer.models.results import LoadDistributionResult

# ---------------------------------------------------------------------------
# LaTeX formula strings
# ---------------------------------------------------------------------------
FORMULA_AXIAL_PER_BOLT = r"F_{A,i} = \frac{F_{total}}{n_B}"
FORMULA_BENDING_PER_BOLT = r"F_{B,i} = \frac{M_B \cdot x_i}{\sum_j x_j^2}"
FORMULA_SHEAR_PER_BOLT = r"V_i = \frac{V_{total}}{n_B} + \frac{M_T \cdot r_i}{\sum_j r_j^2}"
FORMULA_TOTAL_AXIAL = r"F_{tot,crit} = F_{A,i} + F_{B,i}"


def _axial_forces(
    positions: List[Tuple[float, float]],
    F_axial: float,
    M_bend: float,
) -> List[float]:
    """Per-bolt axial force from membrane + bending about the centroid."""
    n = len(positions)
    F_each = F_axial / n
    sum_x2 = sum(x * x for x, _ in positions)
    if sum_x2 <= 0:
        return [F_each for _ in positions]
    return [F_each + M_bend * x / sum_x2 for x, _ in positions]


def calculate_load_distribution(
    bolt_circle: BoltCircle,
    loading: ExternalLoading,
) -> LoadDistributionResult:
    """Distribute external loads onto individual bolts of the pattern.

    The bolt most loaded in axial tension (axial + bending) is the
    critical bolt.  The minimum load set (axial_force_min /
    bending_moment_min) is evaluated on the SAME bolt for the fatigue
    amplitude.  The per-bolt shear reported is the worst combination of
    direct share and torsion-induced tangential share.

    Args:
        bolt_circle: Bolt pattern definition (circle / rectangle / custom).
        loading: External loading including load factor.

    Returns:
        LoadDistributionResult identifying the critical bolt and its loads.
    """
    positions = bolt_circle.bolt_positions()
    n_B = len(positions)

    # Factored loads
    lf = loading.load_factor
    F_axial = loading.axial_force * lf       # [N]
    M_bend = loading.bending_moment * lf     # [N·mm]
    V_shear = loading.shear_force * lf       # [N]
    M_tors = loading.torsion * lf            # [N·mm]
    F_axial_min = loading.axial_force_min * lf
    M_bend_min = loading.bending_moment_min * lf

    angles_deg = [math.degrees(math.atan2(y, x)) % 360.0 for x, y in positions]
    F_axial_each = F_axial / n_B

    # --- Axial + bending, maximum load set ---
    bolt_axial_forces = _axial_forces(positions, F_axial, M_bend)

    # --- Critical bolt (worst-case axial tension) ---
    critical_idx = int(bolt_axial_forces.index(max(bolt_axial_forces)))
    F_total_axial = bolt_axial_forces[critical_idx]
    F_bend_crit = F_total_axial - F_axial_each

    # --- Minimum load set on the SAME bolt (fatigue amplitude) ---
    bolt_axial_forces_min = _axial_forces(positions, F_axial_min, M_bend_min)
    F_total_axial_min = bolt_axial_forces_min[critical_idx]

    # --- Shear per bolt: direct share + torsion-induced tangential share ---
    V_direct = abs(V_shear) / n_B
    sum_r2 = sum(x * x + y * y for x, y in positions)
    if M_tors != 0.0 and sum_r2 > 0:
        r_max = max(math.hypot(x, y) for x, y in positions)
        V_torsion = abs(M_tors) * r_max / sum_r2
    else:
        V_torsion = 0.0
    # Conservative scalar combination (directions not tracked)
    V_per_bolt = V_direct + V_torsion

    return LoadDistributionResult(
        critical_bolt_index=critical_idx,
        F_axial_per_bolt=F_axial_each,
        F_bend_per_bolt=F_bend_crit,
        V_shear_per_bolt=V_per_bolt,
        F_total_axial=F_total_axial,
        bolt_angles_deg=angles_deg,
        bolt_axial_forces=bolt_axial_forces,
        V_direct_per_bolt=V_direct,
        V_torsion_per_bolt=V_torsion,
        F_total_axial_min=F_total_axial_min,
        bolt_positions=[(round(x, 6), round(y, 6)) for x, y in positions],
    )

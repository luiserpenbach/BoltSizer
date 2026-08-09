"""Bolt circle load distribution — axial + bending + shear + torsion.

For a symmetric bolt circle under combined loading, each bolt i is located
at angle θ_i from the bending axis.  The load distribution assumptions:
  - Axial (membrane): equal share per bolt.
  - Bending: bolt load proportional to radial position × cos(θ_i).
    (Rigid flange, elastic bolts — standard structural assumption.)
  - Shear: equal share per bolt (friction-reacted or pin-reacted).
  - Torsion about the circle axis: tangential shear V_t = M_T/(n_B·r)
    per bolt, combined with the direct shear share by scalar addition
    (conservative upper bound — the direct-shear direction relative to
    the pattern is not tracked).

Reference:
  Bickford, "An Introduction to the Design and Behavior of Bolted Joints",
  4th ed., §6 — bolt circle moment resolution.
  ECSS-E-HB-32-23A §8 — bolt group analysis.

Sign convention: tension positive, bolts numbered 0..n-1 starting at θ=0.
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
FORMULA_BENDING_PER_BOLT = (
    r"F_{B,i} = \frac{M_B \cdot r_i \cos\theta_i}{\sum_j r_j^2 \cos^2\!\theta_j}"
)
FORMULA_SHEAR_PER_BOLT = r"V_i = \frac{V_{total}}{n_B} + \frac{M_T}{n_B \cdot r}"
FORMULA_TOTAL_AXIAL = r"F_{tot,crit} = F_{A,i} + F_{B,i}"


def _axial_forces(
    n_B: int,
    r: float,
    F_axial: float,
    M_bend: float,
    angles_rad: List[float],
) -> List[float]:
    """Per-bolt axial force from membrane + bending distribution."""
    F_axial_each = F_axial / n_B
    denom = sum(r ** 2 * math.cos(a) ** 2 for a in angles_rad)
    if denom == 0:
        # Degenerate case (r = 0): bending cannot be resolved by the pattern
        denom = 1.0
    return [F_axial_each + M_bend * r * math.cos(a) / denom for a in angles_rad]


def calculate_load_distribution(
    bolt_circle: BoltCircle,
    loading: ExternalLoading,
) -> LoadDistributionResult:
    """Distribute external loads onto individual bolts in the bolt circle.

    The bolt most loaded in axial tension (axial + bending contributions)
    is identified as the critical bolt.  The minimum load set
    (axial_force_min / bending_moment_min) is evaluated on the SAME bolt
    for the fatigue amplitude.

    Args:
        bolt_circle: Bolt circle geometry (n_B bolts on PCD).
        loading: External loading including load factor.

    Returns:
        LoadDistributionResult identifying the critical bolt and its loads.
    """
    n_B = bolt_circle.num_bolts
    r = bolt_circle.bolt_circle_diameter / 2.0  # Bolt circle radius [mm]

    # Factored loads
    lf = loading.load_factor
    F_axial = loading.axial_force * lf       # [N]
    M_bend = loading.bending_moment * lf     # [N·mm]
    V_shear = loading.shear_force * lf       # [N]
    M_tors = loading.torsion * lf            # [N·mm]
    F_axial_min = loading.axial_force_min * lf
    M_bend_min = loading.bending_moment_min * lf

    # Bolt angles: evenly spaced, starting at 0°
    # Bending axis is horizontal (θ measured from top-dead-centre of bending).
    angles_deg = [360.0 * i / n_B for i in range(n_B)]
    angles_rad = [math.radians(a) for a in angles_deg]

    F_axial_each = F_axial / n_B

    # --- Axial + bending, maximum load set ---
    bolt_axial_forces = _axial_forces(n_B, r, F_axial, M_bend, angles_rad)

    # --- Critical bolt (worst-case axial tension) ---
    critical_idx = int(bolt_axial_forces.index(max(bolt_axial_forces)))
    F_total_axial = bolt_axial_forces[critical_idx]
    F_bend_crit = F_total_axial - F_axial_each

    # --- Minimum load set on the SAME bolt (fatigue amplitude) ---
    bolt_axial_forces_min = _axial_forces(n_B, r, F_axial_min, M_bend_min, angles_rad)
    F_total_axial_min = bolt_axial_forces_min[critical_idx]

    # --- Shear per bolt: direct share + torsion-induced tangential share ---
    V_direct = abs(V_shear) / n_B
    if M_tors != 0.0 and r > 0:
        V_torsion = abs(M_tors) / (n_B * r)
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
    )

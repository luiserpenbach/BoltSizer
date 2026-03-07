"""Bolt circle load distribution — axial + bending + shear.

For a symmetric bolt circle under combined loading, each bolt i is located
at angle θ_i from the bending axis.  The load distribution assumptions:
  - Axial (membrane): equal share per bolt.
  - Bending: bolt load proportional to radial position × cos(θ_i).
    (Rigid flange, elastic bolts — standard structural assumption.)
  - Shear: equal share per bolt (friction-reacted or pin-reacted).

Reference:
  Bickford, "An Introduction to the Design and Behavior of Bolted Joints",
  4th ed., §6 — bolt circle moment resolution.
  ECSS-E-HB-32-23A §8 — bolt group analysis.

Sign convention: tension positive, bolts numbered 0..n-1 starting at θ=0.
"""
from __future__ import annotations
import math
from typing import List
from boltsizer.models.joint import BoltCircle, ExternalLoading
from boltsizer.models.results import LoadDistributionResult

# ---------------------------------------------------------------------------
# LaTeX formula strings
# ---------------------------------------------------------------------------
FORMULA_AXIAL_PER_BOLT = r"F_{A,i} = \frac{F_{total}}{n_B}"
FORMULA_BENDING_PER_BOLT = (
    r"F_{B,i} = \frac{M_B \cdot r_i \cos\theta_i}{\sum_j r_j^2 \cos^2\!\theta_j}"
)
FORMULA_SHEAR_PER_BOLT = r"V_i = \frac{V_{total}}{n_B}"
FORMULA_TOTAL_AXIAL = r"F_{tot,crit} = F_{A,i} + F_{B,i}"


def calculate_load_distribution(
    bolt_circle: BoltCircle,
    loading: ExternalLoading,
) -> LoadDistributionResult:
    """Distribute external loads onto individual bolts in the bolt circle.

    The bolt most loaded in axial tension (axial + bending contributions)
    is identified as the critical bolt.

    VDI 2230 (2014) §4, Bickford §6.

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

    # Bolt angles: evenly spaced, starting at 0°
    # Bending axis is horizontal (θ measured from top-dead-centre of bending).
    angles_deg = [360.0 * i / n_B for i in range(n_B)]
    angles_rad = [math.radians(a) for a in angles_deg]

    # --- Axial load per bolt (membrane) ---
    F_axial_each = F_axial / n_B

    # --- Bending contribution per bolt ---
    # Σ r_j² cos²(θ_j)  — denominator for bending distribution
    denom = sum(r ** 2 * math.cos(a) ** 2 for a in angles_rad)
    if denom == 0:
        # Degenerate case (single bolt or symmetrical cancellation)
        denom = 1.0

    F_bend_each: List[float] = []
    for a in angles_rad:
        f_b_i = M_bend * r * math.cos(a) / denom
        F_bend_each.append(f_b_i)

    # Total axial force on each bolt
    bolt_axial_forces: List[float] = [
        F_axial_each + F_bend_each[i] for i in range(n_B)
    ]

    # --- Critical bolt (worst-case axial tension) ---
    critical_idx = int(bolt_axial_forces.index(max(bolt_axial_forces)))
    F_total_axial = bolt_axial_forces[critical_idx]

    # --- Shear per bolt ---
    V_per_bolt = V_shear / n_B

    return LoadDistributionResult(
        critical_bolt_index=critical_idx,
        F_axial_per_bolt=F_axial_each,
        F_bend_per_bolt=F_bend_each[critical_idx],
        V_shear_per_bolt=V_per_bolt,
        F_total_axial=F_total_axial,
        bolt_angles_deg=angles_deg,
        bolt_axial_forces=bolt_axial_forces,
    )

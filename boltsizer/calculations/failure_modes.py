"""Failure mode margin of safety calculations.

All margins defined as MS = (allowable / applied) - 1.
Positive MS → PASS.  ECSS minimum acceptable MS = 0.0.

Failure modes implemented:
  1. Yield at assembly (bolt stressed by tightening only).
  2. Yield under combined load (axial preload + external fraction + torsion).
  3. Joint separation (clamping force drops to zero).
  4. Interface slip (friction overcome by shear).
  5. Bolt shear (direct shear through bolt cross-section).
  6. Bearing (plate bearing stress under bolt).
  7. Fatigue (bolt load amplitude vs. allowable).

Reference equations cited throughout.

Sign convention: tension positive.
Units: N, mm, MPa.
"""
from __future__ import annotations
import math
from typing import List, Literal, Optional
from boltsizer.models.bolt import Bolt
from boltsizer.models.joint import BoltCircle, ClampedInterface, ExternalLoading
from boltsizer.models.results import MarginOfSafety, PreloadResult, StiffnessResult, LoadDistributionResult

# ---------------------------------------------------------------------------
# LaTeX formulas (module-level, kept adjacent for traceability)
# ---------------------------------------------------------------------------
_LATEX = {
    "yield_assembly": (
        r"MS_{yield,asm} = \frac{0.9 \cdot F_{proof}}{F_{M,\max}} - 1"
    ),
    "yield_combined": (
        r"MS_{yield,comb} = \frac{0.9 \cdot A_S \cdot \sigma_y}"
        r"{\sqrt{F_{bolt,\max}^2 + (M_T / W_p)^2 \cdot A_S^2}} - 1"
    ),
    "separation": (
        r"MS_{sep} = \frac{F_{V,\min}}{F_{ext} \cdot (1 - \varphi_n)} - 1"
    ),
    "slip": (
        r"MS_{slip} = \frac{\mu \cdot F_{clamp,\min} \cdot n_i}{V_i} - 1"
    ),
    "shear": (
        r"MS_{shear} = \frac{0.6 \cdot A_S \cdot \sigma_y}{V_i} - 1"
    ),
    "bearing": (
        r"MS_{bearing} = \frac{\sigma_{bear,allow} \cdot d \cdot t_{plate}}{V_i} - 1"
    ),
    "fatigue": (
        r"MS_{fatigue} = \frac{\sigma_{a,allow}}{F_{SA} / A_S} - 1"
    ),
}

# Bearing stress allowable factor: σ_bear = 1.5 · σ_y (structural steel convention)
_BEARING_FACTOR = 1.5


def _ms(allowable: float, applied: float) -> float:
    """Compute margin of safety = allowable/applied - 1."""
    if applied == 0:
        return float("inf")
    return allowable / applied - 1.0


def _status(ms: float, min_ms: float = 0.0) -> Literal["PASS", "FAIL", "WARNING"]:
    if ms < min_ms:
        return "FAIL"
    if ms < 0.25:
        return "WARNING"
    return "PASS"


def check_yield_assembly(
    bolt: Bolt,
    preload: PreloadResult,
) -> MarginOfSafety:
    """Check bolt yield during assembly (tightening).

    Allowable: 90% of proof load force = 0.9 · σ_proof · A_s
    Applied: Maximum assembly preload F_M_max (worst-case tightening).

    VDI 2230 (2014) §5.4.1.

    Args:
        bolt: Bolt specification.
        preload: Preload result containing F_M_max.

    Returns:
        MarginOfSafety for yield at assembly.
    """
    A_s = bolt.geometry.stress_area
    sigma_proof = bolt.material.proof_load_stress or bolt.material.yield_strength
    F_proof = A_s * sigma_proof          # Proof load [N]
    F_allow = 0.9 * F_proof              # 90% utilisation limit

    F_applied = preload.F_M_max

    ms = _ms(F_allow, F_applied)
    return MarginOfSafety(
        check_name="Yield at Assembly",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=F_allow,
        applied=F_applied,
        unit="N",
        explanation=(
            f"Assembly preload {F_applied:.0f} N vs. 90% of proof load "
            f"{F_allow:.0f} N (σ_proof = {sigma_proof:.0f} MPa, "
            f"A_s = {A_s:.1f} mm²)."
        ),
        formula_latex=_LATEX["yield_assembly"],
    )


def check_yield_combined(
    bolt: Bolt,
    preload: PreloadResult,
    stiffness: StiffnessResult,
    F_ext: float,
    M_torsion_thread: float = 0.0,
) -> MarginOfSafety:
    """Check bolt yield under combined bolt load + torsional stress.

    Uses Von Mises criterion:
        σ_v = sqrt(σ_axial² + 3·τ²)
    where τ is torsion in the threaded shank during tightening.

    VDI 2230 (2014) §5.4.2.

    Args:
        bolt: Bolt specification.
        preload: Preload result.
        stiffness: Stiffness result for φ_n.
        F_ext: Total external axial force on the critical bolt [N].
        M_torsion_thread: Torsional moment in threaded section [N·mm].
            Typically M_A · d_2 / (2 · K_total) or passed as 0 post-assembly.

    Returns:
        MarginOfSafety for yield under combined load.
    """
    geom = bolt.geometry
    mat = bolt.material
    A_s = geom.stress_area
    sigma_y = mat.yield_strength

    # Maximum bolt load = preload + φ_n · F_ext (VDI 2230 §5.3.1)
    F_bolt_max = preload.F_M_max + stiffness.phi_n * max(0.0, F_ext)

    # Axial stress
    sigma_axial = F_bolt_max / A_s

    # Torsional stress in minor diameter (VDI 2230 §5.4.2)
    d3 = geom.minor_diameter
    W_p = math.pi * d3 ** 3 / 16          # Polar section modulus [mm³]
    tau = M_torsion_thread / W_p if (W_p > 0 and M_torsion_thread > 0) else 0.0

    # Von Mises equivalent stress
    sigma_v = math.sqrt(sigma_axial ** 2 + 3 * tau ** 2)
    sigma_allow = 0.9 * sigma_y

    ms = _ms(sigma_allow, sigma_v)
    return MarginOfSafety(
        check_name="Yield (Combined Load)",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=sigma_allow,
        applied=sigma_v,
        unit="MPa",
        explanation=(
            f"Von Mises stress {sigma_v:.1f} MPa (σ_axial = {sigma_axial:.1f} MPa, "
            f"τ = {tau:.1f} MPa) vs. allowable 0.9·σ_y = {sigma_allow:.1f} MPa."
        ),
        formula_latex=_LATEX["yield_combined"],
    )


def check_joint_separation(
    preload: PreloadResult,
    stiffness: StiffnessResult,
    F_ext: float,
    standard: Literal["VDI", "ECSS"] = "VDI",
) -> MarginOfSafety:
    """Check joint separation (interface opening).

    Condition: clamping force must remain positive.
        F_clamp = F_V_min - F_ext · (1 - φ_n)  ≥ 0

    ECSS convention (conservative): uses F_M_min without embedding loss.
    VDI convention: uses net minimum preload after embedding.

    VDI 2230 (2014) §5.4.3; ECSS-E-HB-32-23A §8.3.

    Args:
        preload: Preload result.
        stiffness: Stiffness result.
        F_ext: Total external opening (axial) force on bolt [N].
        standard: "VDI" or "ECSS" — changes minimum preload definition.

    Returns:
        MarginOfSafety for joint separation.
    """
    if standard == "ECSS":
        F_V_min = preload.F_M_min  # ECSS: without embedding (conservative)
    else:
        F_V_min = preload.F_preload_min  # VDI: after embedding loss

    # Reduction of clamping force by external load
    # Allowable (clamping preload): F_V_min
    # Applied (opening demand):     F_ext · (1 - φ_n)
    F_opening_demand = max(0.0, F_ext) * (1.0 - stiffness.phi_n)

    ms = _ms(F_V_min, F_opening_demand) if F_opening_demand > 0 else float("inf")

    return MarginOfSafety(
        check_name="Joint Separation",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=F_V_min,
        applied=F_opening_demand,
        unit="N",
        explanation=(
            f"Min clamping force {F_V_min:.0f} N vs. opening demand "
            f"F_ext·(1-φ_n) = {F_ext:.0f}·(1-{stiffness.phi_n:.3f}) = "
            f"{F_opening_demand:.0f} N [{standard} convention]."
        ),
        formula_latex=_LATEX["separation"],
    )


def check_slip(
    preload: PreloadResult,
    F_ext: float,
    stiffness: StiffnessResult,
    friction_coeff: float,
    num_friction_interfaces: int,
    V_shear: float,
) -> MarginOfSafety:
    """Check interface slip (shear friction).

    Allowable slip force = μ · F_clamp_min · n_interfaces
    F_clamp_min at bolt = F_V_min - F_ext·(1-φ_n)  (remaining clamping force)

    VDI 2230 (2014) §5.4.4.

    Args:
        preload: Preload result.
        F_ext: Axial external force on the critical bolt [N].
        stiffness: Stiffness result for φ_n.
        friction_coeff: Interface friction coefficient μ.
        num_friction_interfaces: n_i (number of slip interfaces).
        V_shear: Shear force on the critical bolt [N].

    Returns:
        MarginOfSafety for slip.
    """
    # Remaining clamping force after external axial load
    F_clamp_min = max(0.0, preload.F_preload_min - F_ext * (1.0 - stiffness.phi_n))

    slip_capacity = friction_coeff * F_clamp_min * num_friction_interfaces
    V_applied = abs(V_shear)

    ms = _ms(slip_capacity, V_applied) if V_applied > 0 else float("inf")

    return MarginOfSafety(
        check_name="Interface Slip",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=slip_capacity,
        applied=V_applied,
        unit="N",
        explanation=(
            f"Slip capacity μ·F_clamp·n_i = {friction_coeff:.2f}·{F_clamp_min:.0f}"
            f"·{num_friction_interfaces} = {slip_capacity:.0f} N "
            f"vs. shear {V_applied:.0f} N."
        ),
        formula_latex=_LATEX["slip"],
    )


def check_bolt_shear(
    bolt: Bolt,
    V_shear: float,
) -> MarginOfSafety:
    """Check bolt direct shear capacity.

    Allowable: 0.6 · A_s · σ_y  (Tresca criterion)
    Applied: Shear force on bolt V_shear.

    VDI 2230 (2014) §5.4.5; general structural practice.

    Args:
        bolt: Bolt specification.
        V_shear: Shear force on the bolt [N].

    Returns:
        MarginOfSafety for bolt shear.
    """
    A_s = bolt.geometry.stress_area
    sigma_y = bolt.material.yield_strength
    V_allow = 0.6 * A_s * sigma_y
    V_applied = abs(V_shear)

    ms = _ms(V_allow, V_applied) if V_applied > 0 else float("inf")

    return MarginOfSafety(
        check_name="Bolt Shear",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=V_allow,
        applied=V_applied,
        unit="N",
        explanation=(
            f"Shear capacity 0.6·A_s·σ_y = 0.6·{A_s:.1f}·{sigma_y:.0f} = "
            f"{V_allow:.0f} N vs. applied {V_applied:.0f} N."
        ),
        formula_latex=_LATEX["shear"],
    )


def check_bearing(
    bolt: Bolt,
    V_shear: float,
    plate_thickness: float,
    plate_yield_strength: float,
) -> MarginOfSafety:
    """Check bearing stress in the clamped plate.

    Allowable bearing stress: σ_bear = 1.5 · σ_y_plate
    Bearing area: A_bear = d · t_plate
    Applied bearing stress: V_shear / A_bear

    Args:
        bolt: Bolt specification.
        V_shear: Shear force on bolt [N].
        plate_thickness: Thinnest plate thickness [mm].
        plate_yield_strength: Plate material yield strength [MPa].

    Returns:
        MarginOfSafety for bearing.
    """
    d = bolt.geometry.nominal_diameter
    A_bear = d * plate_thickness
    sigma_allow = _BEARING_FACTOR * plate_yield_strength

    V_applied = abs(V_shear)
    sigma_applied = V_applied / A_bear if A_bear > 0 else float("inf")

    ms = _ms(sigma_allow, sigma_applied) if sigma_applied > 0 else float("inf")

    return MarginOfSafety(
        check_name="Bearing (Plate)",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=sigma_allow,
        applied=sigma_applied,
        unit="MPa",
        explanation=(
            f"Bearing stress {sigma_applied:.1f} MPa vs. allowable "
            f"1.5·σ_y_plate = {sigma_allow:.1f} MPa "
            f"(d={d:.1f} mm, t={plate_thickness:.1f} mm)."
        ),
        formula_latex=_LATEX["bearing"],
    )


def check_fatigue(
    bolt: Bolt,
    stiffness: StiffnessResult,
    F_ext_amplitude: float,
) -> Optional[MarginOfSafety]:
    """Check bolt fatigue (infinite life).

    Bolt load amplitude: F_SA = φ_n · F_ext_amplitude / 2
    Allowable stress amplitude: σ_a from material fatigue limit.

    VDI 2230 (2014) §5.4.6.

    Args:
        bolt: Bolt specification.
        stiffness: Stiffness result.
        F_ext_amplitude: Amplitude of external bolt load F_ext [N].
                         (For fully reversed loading, = F_ext_max.)

    Returns:
        MarginOfSafety for fatigue, or None if no fatigue limit defined.
    """
    if bolt.material.fatigue_limit is None:
        return None

    A_s = bolt.geometry.stress_area
    sigma_a_allow = bolt.material.fatigue_limit

    # VDI 2230 §5.4.6: load amplitude in bolt
    F_SA = stiffness.phi_n * F_ext_amplitude / 2.0
    sigma_a_applied = F_SA / A_s if A_s > 0 else 0.0

    ms = _ms(sigma_a_allow, sigma_a_applied) if sigma_a_applied > 0 else float("inf")

    return MarginOfSafety(
        check_name="Fatigue (Infinite Life)",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=sigma_a_allow,
        applied=sigma_a_applied,
        unit="MPa",
        explanation=(
            f"Bolt stress amplitude {sigma_a_applied:.1f} MPa "
            f"(F_SA = φ_n·F_ext/2 = {stiffness.phi_n:.3f}·{F_ext_amplitude:.0f}/2 = {F_SA:.0f} N) "
            f"vs. fatigue limit {sigma_a_allow:.1f} MPa."
        ),
        formula_latex=_LATEX["fatigue"],
    )


def calculate_all_margins(
    bolt: Bolt,
    preload: PreloadResult,
    stiffness: StiffnessResult,
    load_dist: LoadDistributionResult,
    interface: ClampedInterface,
    loading: ExternalLoading,
    plate_thickness: float = 10.0,
    plate_yield_strength: float = 240.0,
    standard: Literal["VDI", "ECSS"] = "VDI",
    M_torsion_thread: float = 0.0,
) -> List[MarginOfSafety]:
    """Calculate all failure mode margins for a single load case.

    Args:
        bolt: Bolt specification.
        preload: Preload calculation result.
        stiffness: Stiffness calculation result.
        load_dist: Load distribution result (critical bolt loads).
        interface: Clamped interface definition.
        loading: External loading.
        plate_thickness: Thinnest plate for bearing check [mm].
        plate_yield_strength: Plate yield strength for bearing [MPa].
        standard: "VDI" or "ECSS" convention.
        M_torsion_thread: Residual torsion in bolt thread [N·mm] (0 post-assembly).

    Returns:
        List of MarginOfSafety, sorted worst-first, with binding flag set.
    """
    F_ext = load_dist.F_total_axial   # Total external axial on critical bolt [N]
    V_shear = load_dist.V_shear_per_bolt

    margins: List[MarginOfSafety] = []

    # 1. Yield at assembly
    margins.append(check_yield_assembly(bolt, preload))

    # 2. Yield under combined load
    margins.append(check_yield_combined(bolt, preload, stiffness, F_ext, M_torsion_thread))

    # 3. Joint separation
    margins.append(check_joint_separation(preload, stiffness, F_ext, standard))

    # 4. Slip
    margins.append(check_slip(
        preload, F_ext, stiffness,
        interface.friction_coefficient,
        interface.num_friction_interfaces,
        V_shear,
    ))

    # 5. Bolt shear
    margins.append(check_bolt_shear(bolt, V_shear))

    # 6. Bearing
    margins.append(check_bearing(bolt, V_shear, plate_thickness, plate_yield_strength))

    # 7. Fatigue
    fatigue_ms = check_fatigue(bolt, stiffness, abs(F_ext))
    if fatigue_ms is not None:
        margins.append(fatigue_ms)

    # Sort worst-first; cap inf for comparison
    margins.sort(key=lambda m: m.value if m.value != float("inf") else 1e9)

    # Flag the binding constraint (lowest finite margin)
    finite = [m for m in margins if m.value != float("inf")]
    if finite:
        finite[0].binding = True

    return margins

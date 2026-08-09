"""Failure mode margin of safety calculations.

All margins defined as MS = allowable / (FoS · applied) - 1.
Positive MS → PASS.  Minimum acceptable MS = 0.0.

Failure modes implemented:
  1.  Yield at assembly — von Mises with tightening torsion (VDI §5.5.1).
  2.  Yield under working load — axial + 50% residual torsion (VDI §5.5.2).
  3.  Ultimate under working load (ECSS ultimate margin, FOSU).
  4.  Joint separation (clamping force drops to zero).
  5.  Interface slip (friction overcome by shear).
  6.  Bolt shear (yield + ultimate, through-thread section A_d3).
  7.  Bearing (plate bearing stress under bolt).
  8.  Surface pressure under head/nut (VDI §5.5.4 style).
  9.  Fatigue — VDI 2230 §5.5.3 thread endurance (σ_ASV / σ_ASG).
  10. Thread stripping (tapped joints, optional).

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
        r"MS = \frac{0.9\,\sigma_y}{\sqrt{\sigma_M^2 + 3\tau_M^2}} - 1"
    ),
    "yield_combined": (
        r"MS = \frac{\sigma_y}{FoS_y\,\sqrt{\sigma_z^2 + 3(0.5\,\tau_M)^2}} - 1"
    ),
    "ultimate_combined": (
        r"MS = \frac{\sigma_u}{FoS_u\,\sqrt{\sigma_z^2 + 3(0.5\,\tau_M)^2}} - 1"
    ),
    "separation": (
        r"MS = \frac{F_{V,\min}}{FoS_{sep}\,F_{ext}\,(1 - \varphi_n)} - 1"
    ),
    "slip": (
        r"MS = \frac{\mu \cdot F_{K,\min} \cdot n_i}{FoS_{slip}\,V_i} - 1"
    ),
    "shear_yield": (
        r"MS = \frac{0.577\,\sigma_y\,A_{d3}}{V_i} - 1"
    ),
    "shear_ultimate": (
        r"MS = \frac{0.577\,\sigma_u\,A_{d3}}{FoS_u\,V_i} - 1"
    ),
    "bearing": (
        r"MS = \frac{1.5\,\sigma_{y,plate}}{V_i / (d \cdot t)} - 1"
    ),
    "surface_pressure": (
        r"MS = \frac{p_G}{F_{S,\max} / A_p} - 1"
    ),
    "fatigue": (
        r"MS = \frac{\sigma_{AS}}{\sigma_a},\quad"
        r"\sigma_a = \frac{\varphi_n (F_{max} - F_{min})}{2 A_S}"
    ),
    "stripping": (
        r"MS = \frac{0.577\,\sigma_u\,A_{th}}{FoS_u\,F_{S,\max}} - 1"
    ),
}

# Bearing stress allowable factor: σ_bear = 1.5 · σ_y (structural convention)
_BEARING_FACTOR = 1.5
# Residual thread torsion fraction in the working state (VDI 2230 §5.5.2)
_RESIDUAL_TORSION_FRACTION = 0.5
# Assembly utilisation factor ν (VDI 2230 §5.5.1)
_ASSEMBLY_UTILISATION = 0.9


def _ms(allowable: float, applied: float, fos: float = 1.0) -> float:
    """Compute margin of safety = allowable/(fos·applied) - 1."""
    if applied == 0:
        return float("inf")
    return allowable / (fos * applied) - 1.0


def _status(ms: float, min_ms: float = 0.0) -> Literal["PASS", "FAIL", "WARNING"]:
    if ms < min_ms:
        return "FAIL"
    if ms < 0.25:
        return "WARNING"
    return "PASS"


def compute_thread_torque(bolt: Bolt, nut_factor_K: float, F_M: float) -> float:
    """Thread (pitch + thread-friction) torque M_G [N·mm] at preload F_M.

    The total torque splits into thread torque and under-head friction:
        M_A = F_M·(0.159·P + 0.578·d₂·μ_G + 0.5·D_Km·μ_K)
    Only M_G = F_M·(0.159·P + 0.578·d₂·μ_G) twists the bolt shank.

    The effective friction coefficient is derived from the nut factor
    assuming μ_G = μ_K = μ:
        μ = (K·d − 0.159·P) / (0.578·d₂ + 0.5·D_Km)
    with D_Km = (d_w + d_h)/2 the effective bearing friction diameter.

    Args:
        bolt: Bolt specification.
        nut_factor_K: Nut factor used for the torque conversion.
        F_M: Preload at which to evaluate the thread torque [N].

    Returns:
        Thread torque M_G [N·mm] (≥ 0).
    """
    geom = bolt.geometry
    d = geom.nominal_diameter
    P = geom.pitch
    d2 = geom.pitch_diameter
    D_Km = 0.5 * (geom.head_bearing_diameter + geom.hole_diameter)

    mu = (nut_factor_K * d - 0.159 * P) / (0.578 * d2 + 0.5 * D_Km)
    mu = max(0.0, mu)
    return F_M * (0.159 * P + 0.578 * d2 * mu)


def _thread_shear_stress(bolt: Bolt, M_G: float) -> float:
    """Torsional shear stress τ [MPa] in the thread from thread torque M_G.

    Uses the stress diameter d_s = (d2 + d3)/2 per VDI 2230 §5.5.1:
        W_p = π·d_s³/16,  τ = M_G / W_p
    """
    d_s = bolt.geometry.stress_diameter
    W_p = math.pi * d_s ** 3 / 16.0
    return M_G / W_p if W_p > 0 else 0.0


def _assembly_equivalent_stress(
    bolt: Bolt,
    preload: PreloadResult,
    nut_factor_K: Optional[float],
) -> tuple:
    """Assembly (installation) von Mises stress.

    σ_red,M = sqrt(σ_M² + 3·τ_M²) with σ_M = F_M_max/A_s and τ_M from the
    thread torque evaluated at the SAME friction state that produces
    F_M_max (i.e. K_min when a friction range is given) — the physically
    consistent worst pairing.

    Returns (sigma_red, sigma_M, tau_M).
    """
    A_s = bolt.geometry.stress_area
    F_applied = preload.F_M_max
    sigma_M = F_applied / A_s if A_s > 0 else 0.0

    if nut_factor_K is not None and nut_factor_K > 0:
        M_G = compute_thread_torque(bolt, nut_factor_K, F_applied)
        tau_M = _thread_shear_stress(bolt, M_G)
    else:
        tau_M = 0.0

    return math.sqrt(sigma_M ** 2 + 3.0 * tau_M ** 2), sigma_M, tau_M


def check_yield_assembly(
    bolt: Bolt,
    preload: PreloadResult,
    nut_factor_K: Optional[float] = None,
    nu: float = _ASSEMBLY_UTILISATION,
    fos: float = 1.0,
) -> MarginOfSafety:
    """Check bolt yield during assembly (tightening) — VDI 2230 §5.5.1 /
    ECSS-E-HB-32-23 §6.3.

    Equivalent stress: σ_red,M = sqrt(σ_M² + 3·τ_M²)
    Allowable: ν·σ_y.  VDI convention: ν = 0.9, FoS = 1.
    ECSS convention: ν = 1.0 with an explicit installation FoS.

    Args:
        bolt: Bolt specification.
        preload: Preload result containing F_M_max.
        nut_factor_K: Nut factor for the thread-torque derivation — pass
            the K matching the max-preload friction state (K_min when a
            range is given).  None → torsion neglected (direct-tension
            tightening methods, e.g. hydraulic tensioner).
        nu: Utilisation factor on σ_y (0.9 VDI, 1.0 ECSS).
        fos: Installation yield factor of safety.

    Returns:
        MarginOfSafety for yield at assembly.
    """
    sigma_y = bolt.material.yield_strength
    sigma_red, sigma_M, tau_M = _assembly_equivalent_stress(bolt, preload, nut_factor_K)
    sigma_allow = nu * sigma_y

    ms = _ms(sigma_allow, sigma_red, fos)
    return MarginOfSafety(
        check_name="Yield at Assembly",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=sigma_allow,
        applied=fos * sigma_red,
        unit="MPa",
        explanation=(
            f"Assembly von Mises stress {sigma_red:.1f} MPa "
            f"(σ_M = {sigma_M:.1f} MPa, τ_M = {tau_M:.1f} MPa) vs. "
            f"allowable {nu:.2f}·σ_y = {sigma_allow:.1f} MPa "
            f"at F_M_max = {preload.F_M_max:.0f} N (FoS {fos:.2f})."
        ),
        formula_latex=_LATEX["yield_assembly"],
    )


def check_ultimate_assembly(
    bolt: Bolt,
    preload: PreloadResult,
    nut_factor_K: Optional[float] = None,
    fos: float = 1.0,
) -> MarginOfSafety:
    """Check bolt ultimate strength during assembly (tightening).

    Same stress state as the assembly yield check (full tightening
    torsion retained — conservative; some tools partially relax the
    torsion for the ultimate installation margin), compared against R_m.

    Returns:
        MarginOfSafety for ultimate at assembly.
    """
    sigma_u = bolt.material.uts
    sigma_red, sigma_M, tau_M = _assembly_equivalent_stress(bolt, preload, nut_factor_K)

    ms = _ms(sigma_u, sigma_red, fos)
    return MarginOfSafety(
        check_name="Ultimate at Assembly",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=sigma_u,
        applied=fos * sigma_red,
        unit="MPa",
        explanation=(
            f"Assembly von Mises stress {sigma_red:.1f} MPa (full tightening "
            f"torsion retained) vs. R_m = {sigma_u:.1f} MPa (FoS {fos:.2f})."
        ),
        formula_latex=_LATEX["ultimate_combined"],
    )


def _working_equivalent_stress(
    bolt: Bolt,
    preload: PreloadResult,
    stiffness: StiffnessResult,
    F_ext: float,
    nut_factor_K: Optional[float],
) -> tuple:
    """Working-state equivalent stress per VDI 2230 §5.5.2.

    Returns (sigma_red_B, sigma_z, tau_residual, F_bolt_max).
    """
    A_s = bolt.geometry.stress_area
    F_bolt_max = preload.F_preload_max + stiffness.phi_n * max(0.0, F_ext)
    sigma_z = F_bolt_max / A_s if A_s > 0 else 0.0

    if nut_factor_K is not None and nut_factor_K > 0:
        M_G = compute_thread_torque(bolt, nut_factor_K, preload.F_M_max)
        tau = _RESIDUAL_TORSION_FRACTION * _thread_shear_stress(bolt, M_G)
    else:
        tau = 0.0

    sigma_red = math.sqrt(sigma_z ** 2 + 3.0 * tau ** 2)
    return sigma_red, sigma_z, tau, F_bolt_max


def check_yield_combined(
    bolt: Bolt,
    preload: PreloadResult,
    stiffness: StiffnessResult,
    F_ext: float,
    nut_factor_K: Optional[float] = None,
    fos_yield: float = 1.0,
) -> MarginOfSafety:
    """Check bolt yield under working load — VDI 2230 §5.5.2.

    Maximum bolt force: F_S_max = F_V_max + φ_n·F_ext.
    Equivalent stress includes 50% residual tightening torsion:
        σ_red,B = sqrt(σ_z² + 3·(0.5·τ_M)²)

    Args:
        bolt: Bolt specification.
        preload: Preload result.
        stiffness: Stiffness result for φ_n.
        F_ext: Total external axial force on the critical bolt [N].
        nut_factor_K: Nut factor for residual-torsion derivation
            (None → no residual torsion).
        fos_yield: Yield factor of safety applied to the stress.

    Returns:
        MarginOfSafety for yield under working load.
    """
    sigma_red, sigma_z, tau, F_bolt_max = _working_equivalent_stress(
        bolt, preload, stiffness, F_ext, nut_factor_K
    )
    sigma_allow = bolt.material.yield_strength

    ms = _ms(sigma_allow, sigma_red, fos_yield)
    return MarginOfSafety(
        check_name="Yield (Working Load)",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=sigma_allow,
        applied=fos_yield * sigma_red,
        unit="MPa",
        explanation=(
            f"Working von Mises stress {sigma_red:.1f} MPa "
            f"(σ_z = {sigma_z:.1f} MPa at F_S_max = {F_bolt_max:.0f} N, "
            f"residual τ = {tau:.1f} MPa) × FoS {fos_yield:.2f} vs. "
            f"σ_y = {sigma_allow:.1f} MPa."
        ),
        formula_latex=_LATEX["yield_combined"],
    )


def check_ultimate_combined(
    bolt: Bolt,
    preload: PreloadResult,
    stiffness: StiffnessResult,
    F_ext: float,
    nut_factor_K: Optional[float] = None,
    fos_ultimate: float = 1.0,
) -> MarginOfSafety:
    """Check bolt ultimate strength under working load (ECSS ultimate margin).

    Same stress state as the yield check, compared against R_m with the
    ultimate factor of safety.

    Returns:
        MarginOfSafety for ultimate strength.
    """
    sigma_red, sigma_z, tau, F_bolt_max = _working_equivalent_stress(
        bolt, preload, stiffness, F_ext, nut_factor_K
    )
    sigma_allow = bolt.material.uts

    ms = _ms(sigma_allow, sigma_red, fos_ultimate)
    return MarginOfSafety(
        check_name="Ultimate (Working Load)",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=sigma_allow,
        applied=fos_ultimate * sigma_red,
        unit="MPa",
        explanation=(
            f"Working von Mises stress {sigma_red:.1f} MPa × FoS_u "
            f"{fos_ultimate:.2f} vs. R_m = {sigma_allow:.1f} MPa."
        ),
        formula_latex=_LATEX["ultimate_combined"],
    )


def check_joint_separation(
    preload: PreloadResult,
    stiffness: StiffnessResult,
    F_ext: float,
    standard: Literal["VDI", "ECSS"] = "VDI",
    fos_separation: float = 1.0,
) -> MarginOfSafety:
    """Check joint separation (interface opening).

    Condition: residual clamping force must remain positive:
        F_K = F_V_min − F_ext·(1 − φ_n) ≥ 0

    The minimum preload F_V_min includes ALL preload losses (tightening
    scatter, embedding, thermal) under BOTH conventions — ignoring a loss
    would overstate the separation margin.  (ECSS additionally applies a
    separation factor of safety, passed as fos_separation.)

    VDI 2230 (2014) §5.5; ECSS-E-HB-32-23A §6.3.

    Args:
        preload: Preload result (F_preload_min = after losses).
        stiffness: Stiffness result.
        F_ext: Total external opening (axial) force on bolt [N].
        standard: "VDI" or "ECSS" — label only; both use after-loss preload.
        fos_separation: Separation (gapping) factor of safety.

    Returns:
        MarginOfSafety for joint separation.
    """
    F_V_min = preload.F_preload_min  # after scatter + embedding (+ thermal)

    # Opening demand from external load
    F_opening_demand = max(0.0, F_ext) * (1.0 - stiffness.phi_n)

    ms = _ms(F_V_min, F_opening_demand, fos_separation) if F_opening_demand > 0 else float("inf")

    return MarginOfSafety(
        check_name="Joint Separation",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=F_V_min,
        applied=fos_separation * F_opening_demand,
        unit="N",
        explanation=(
            f"Min preload after losses {F_V_min:.0f} N vs. opening demand "
            f"FoS·F_ext·(1-φ_n) = {fos_separation:.2f}·{F_ext:.0f}"
            f"·(1-{stiffness.phi_n:.3f}) = {fos_separation * F_opening_demand:.0f} N "
            f"[{standard}]."
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
    fos_slip: float = 1.0,
) -> MarginOfSafety:
    """Check interface slip (shear friction).

    Allowable slip force = μ · F_clamp_min · n_interfaces
    F_clamp_min at bolt = F_V_min − F_ext·(1−φ_n)  (residual clamping force)

    VDI 2230 (2014) §5.5.6.

    Args:
        preload: Preload result (after-loss minimum).
        F_ext: Axial external force on the critical bolt [N].
        stiffness: Stiffness result for φ_n.
        friction_coeff: Interface friction coefficient μ.
        num_friction_interfaces: n_i (number of slip interfaces).
        V_shear: Shear force on the critical bolt [N] (incl. torsion share).
        fos_slip: Slip factor of safety applied to the shear force.

    Returns:
        MarginOfSafety for slip.
    """
    # Remaining clamping force after external axial load
    F_clamp_min = max(0.0, preload.F_preload_min - max(0.0, F_ext) * (1.0 - stiffness.phi_n))

    slip_capacity = friction_coeff * F_clamp_min * num_friction_interfaces
    V_applied = abs(V_shear)

    ms = _ms(slip_capacity, V_applied, fos_slip) if V_applied > 0 else float("inf")

    return MarginOfSafety(
        check_name="Interface Slip",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=slip_capacity,
        applied=fos_slip * V_applied,
        unit="N",
        explanation=(
            f"Slip capacity μ·F_clamp·n_i = {friction_coeff:.2f}·{F_clamp_min:.0f}"
            f"·{num_friction_interfaces} = {slip_capacity:.0f} N "
            f"vs. shear {fos_slip:.2f}·{V_applied:.0f} N."
        ),
        formula_latex=_LATEX["slip"],
    )


def check_bolt_shear(
    bolt: Bolt,
    V_shear: float,
    shear_plane_in_threads: bool = True,
    fos_ultimate: float = 1.0,
) -> List[MarginOfSafety]:
    """Check bolt direct shear capacity (yield and ultimate).

    Shear area: minor-diameter area A_d3 when the shear plane passes
    through the threads (conservative default), else the shank area A_N.
    Shear strength: 0.577·σ (von Mises).

    Args:
        bolt: Bolt specification.
        V_shear: Shear force on the bolt [N].
        shear_plane_in_threads: True → A_d3, False → shank area A_N.
        fos_ultimate: Ultimate factor of safety for the ultimate margin.

    Returns:
        [MarginOfSafety (yield), MarginOfSafety (ultimate)].
    """
    geom = bolt.geometry
    A_shear = geom.minor_area if shear_plane_in_threads else geom.nominal_area
    plane = "threads (A_d3)" if shear_plane_in_threads else "shank (A_N)"
    sigma_y = bolt.material.yield_strength
    sigma_u = bolt.material.uts
    V_applied = abs(V_shear)

    V_allow_y = 0.577 * A_shear * sigma_y
    ms_y = _ms(V_allow_y, V_applied) if V_applied > 0 else float("inf")
    yield_margin = MarginOfSafety(
        check_name="Bolt Shear (Yield)",
        value=ms_y,
        status=_status(ms_y),
        binding=False,
        allowable=V_allow_y,
        applied=V_applied,
        unit="N",
        explanation=(
            f"Shear yield capacity 0.577·σ_y·A = 0.577·{sigma_y:.0f}·{A_shear:.1f} = "
            f"{V_allow_y:.0f} N vs. applied {V_applied:.0f} N [{plane}]."
        ),
        formula_latex=_LATEX["shear_yield"],
    )

    V_allow_u = 0.577 * A_shear * sigma_u
    ms_u = _ms(V_allow_u, V_applied, fos_ultimate) if V_applied > 0 else float("inf")
    ultimate_margin = MarginOfSafety(
        check_name="Bolt Shear (Ultimate)",
        value=ms_u,
        status=_status(ms_u),
        binding=False,
        allowable=V_allow_u,
        applied=fos_ultimate * V_applied,
        unit="N",
        explanation=(
            f"Shear ultimate capacity 0.577·σ_u·A = 0.577·{sigma_u:.0f}·{A_shear:.1f} = "
            f"{V_allow_u:.0f} N vs. FoS_u·V = {fos_ultimate:.2f}·{V_applied:.0f} N [{plane}]."
        ),
        formula_latex=_LATEX["shear_ultimate"],
    )
    return [yield_margin, ultimate_margin]


def check_bearing(
    bolt: Bolt,
    V_shear: float,
    plate_thickness: float,
    plate_yield_strength: float,
) -> MarginOfSafety:
    """Check bearing stress in the clamped plate.

    Allowable bearing stress: σ_bear = 1.5 · σ_y_plate
    (structural convention; substitute project bearing allowables where
    available).
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


def check_surface_pressure(
    bolt: Bolt,
    preload: PreloadResult,
    stiffness: StiffnessResult,
    F_ext: float,
    surface_pressure_limit: Optional[float],
    plate_yield_strength: float,
) -> MarginOfSafety:
    """Check surface pressure under the bolt head / nut — VDI 2230 §5.5.4.

    Applied: p = max(F_M_max, F_S_max) / A_p
    with A_p = π/4·(d_w² − d_h²) the annular bearing area.
    Allowable: p_G limit of the clamped material.  When no explicit limit
    is given, 1.4·σ_y of the clamped plate is used (documented convention —
    constrained compression sustains more than uniaxial yield; enter the
    VDI 2230 Table A9 value for the actual flange material when known).

    Args:
        bolt: Bolt specification.
        preload: Preload result.
        stiffness: Stiffness result.
        F_ext: External axial force on critical bolt [N].
        surface_pressure_limit: p_G [MPa] or None → 1.4·plate yield.
        plate_yield_strength: Clamped plate yield strength [MPa].

    Returns:
        MarginOfSafety for surface pressure.
    """
    A_p = bolt.geometry.head_bearing_area
    F_working = preload.F_preload_max + stiffness.phi_n * max(0.0, F_ext)
    F_bearing = max(preload.F_M_max, F_working)
    p_applied = F_bearing / A_p if A_p > 0 else float("inf")

    if surface_pressure_limit is not None and surface_pressure_limit > 0:
        p_allow = surface_pressure_limit
        src = "user limit"
    else:
        p_allow = 1.4 * plate_yield_strength
        src = "1.4·σ_y_plate default"

    ms = _ms(p_allow, p_applied) if p_applied > 0 else float("inf")
    return MarginOfSafety(
        check_name="Surface Pressure (Head)",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=p_allow,
        applied=p_applied,
        unit="MPa",
        explanation=(
            f"Head bearing pressure {p_applied:.1f} MPa "
            f"(F = {F_bearing:.0f} N on A_p = {A_p:.1f} mm²) vs. "
            f"p_G = {p_allow:.1f} MPa ({src})."
        ),
        formula_latex=_LATEX["surface_pressure"],
    )


def compute_thread_fatigue_limit(bolt: Bolt, F_Sm: float = 0.0) -> float:
    """Bolt-thread endurance stress amplitude σ_AS [MPa] — VDI 2230 §5.5.3.

    Rolled before heat treatment (standard production):
        σ_ASV = 0.85·(150/d + 45)
    Rolled after heat treatment (aerospace practice):
        σ_ASG = (2 − F_Sm/F_0.2min)·σ_ASV,  factor clamped to [1, 2]

    A user-supplied material.fatigue_limit overrides the computed value
    (for fastener-specific test data only — never smooth-bar values).

    Args:
        bolt: Bolt specification (diameter, rolling condition, material).
        F_Sm: Mean bolt force in service [N] (used for rolled-after-HT).

    Returns:
        Endurance stress amplitude σ_AS [MPa].
    """
    if bolt.material.fatigue_limit is not None:
        return bolt.material.fatigue_limit

    d = bolt.geometry.nominal_diameter
    sigma_ASV = 0.85 * (150.0 / d + 45.0)
    if bolt.thread_rolled == "after_ht":
        F_02 = bolt.material.yield_strength * bolt.geometry.stress_area
        ratio = F_Sm / F_02 if F_02 > 0 else 1.0
        factor = 2.0 - min(max(ratio, 0.0), 1.0)
        return factor * sigma_ASV
    return sigma_ASV


def check_fatigue(
    bolt: Bolt,
    preload: PreloadResult,
    stiffness: StiffnessResult,
    F_ext_max: float,
    F_ext_min: float = 0.0,
) -> MarginOfSafety:
    """Check bolt fatigue (infinite life) — VDI 2230 §5.5.3.

    Bolt stress amplitude:
        σ_a = φ_n·(F_ext_max − F_ext_min) / (2·A_s)
    Allowable: thread endurance limit σ_AS (σ_ASV or σ_ASG).

    Args:
        bolt: Bolt specification.
        preload: Preload result (for the mean force, rolled-after-HT case).
        stiffness: Stiffness result.
        F_ext_max: Maximum external axial force of the cycle on the
            critical bolt [N].
        F_ext_min: Minimum external axial force of the cycle [N]
            (0 = pulsating; −F_ext_max = fully reversed).

    Returns:
        MarginOfSafety for fatigue.
    """
    A_s = bolt.geometry.stress_area

    F_SA = stiffness.phi_n * (F_ext_max - F_ext_min) / 2.0
    F_SA = abs(F_SA)
    sigma_a_applied = F_SA / A_s if A_s > 0 else 0.0

    # Mean bolt force (conservatively high) for the rolled-after-HT benefit
    F_Sm = preload.F_M_max + stiffness.phi_n * (F_ext_max + F_ext_min) / 2.0
    sigma_a_allow = compute_thread_fatigue_limit(bolt, F_Sm)

    ms = _ms(sigma_a_allow, sigma_a_applied) if sigma_a_applied > 0 else float("inf")

    rolled = "rolled after HT" if bolt.thread_rolled == "after_ht" else "rolled before HT"
    src = "user override" if bolt.material.fatigue_limit is not None else f"VDI σ_AS, {rolled}"
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
            f"(F_SA = φ_n·ΔF/2 = {stiffness.phi_n:.3f}·({F_ext_max:.0f}−{F_ext_min:.0f})/2 "
            f"= {F_SA:.0f} N) vs. thread endurance limit {sigma_a_allow:.1f} MPa ({src})."
        ),
        formula_latex=_LATEX["fatigue"],
    )


def check_thread_stripping(
    bolt: Bolt,
    F_bolt_max: float,
    engagement_length: float,
    internal_thread_uts: float,
    fos_ultimate: float = 1.0,
) -> MarginOfSafety:
    """Check thread stripping for tapped joints (no nut).

    Nominal-geometry shear areas per engaged length (Machinery's Handbook
    form, basic dimensions, tolerances neglected):
        internal thread:  A_int = 0.875·π·d·L_e_eff
        external thread:  A_ext = 0.75·π·D1·L_e_eff,  D1 = d − 1.0825·P
    Effective engagement: L_e_eff = L_e − 0.8·P (incomplete end threads).
    Shear strength: 0.577·σ_u of the respective material.

    Standard nuts of matching property class are excluded — ISO 898-2
    proof-load matching prevents stripping; this check applies to tapped
    holes only.

    Args:
        bolt: Bolt specification.
        F_bolt_max: Maximum bolt tension [N].
        engagement_length: Thread engagement length L_e [mm].
        internal_thread_uts: UTS of the tapped (internal thread) material [MPa].
        fos_ultimate: Ultimate factor of safety.

    Returns:
        MarginOfSafety for thread stripping (weaker of the two threads).
    """
    geom = bolt.geometry
    d = geom.nominal_diameter
    P = geom.pitch
    L_e_eff = max(0.0, engagement_length - 0.8 * P)

    D1 = d - 1.0825 * P  # internal thread minor diameter (basic)
    A_int = 0.875 * math.pi * d * L_e_eff
    A_ext = 0.75 * math.pi * D1 * L_e_eff

    cap_int = 0.577 * internal_thread_uts * A_int
    cap_ext = 0.577 * bolt.material.uts * A_ext
    capacity = min(cap_int, cap_ext)
    weaker = "internal (tapped)" if cap_int <= cap_ext else "external (bolt)"

    ms = _ms(capacity, F_bolt_max, fos_ultimate) if F_bolt_max > 0 else float("inf")
    return MarginOfSafety(
        check_name="Thread Stripping",
        value=ms,
        status=_status(ms),
        binding=False,
        allowable=capacity,
        applied=fos_ultimate * F_bolt_max,
        unit="N",
        explanation=(
            f"Stripping capacity {capacity:.0f} N ({weaker} thread governs, "
            f"L_e_eff = {L_e_eff:.1f} mm) vs. FoS_u·F_S_max = "
            f"{fos_ultimate:.2f}·{F_bolt_max:.0f} N."
        ),
        formula_latex=_LATEX["stripping"],
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
    nut_factor_K: Optional[float] = None,
    fos_yield: float = 1.0,
    fos_ultimate: float = 1.0,
    fos_separation: float = 1.0,
    fos_slip: float = 1.0,
    surface_pressure_limit: Optional[float] = None,
    shear_plane_in_threads: bool = True,
    tapped_engagement_length: Optional[float] = None,
    tapped_material_uts: Optional[float] = None,
    assembly_nu: float = _ASSEMBLY_UTILISATION,
    fos_yield_installation: float = 1.0,
    fos_ultimate_installation: float = 1.0,
) -> List[MarginOfSafety]:
    """Calculate all failure mode margins for a single load case.

    Args:
        bolt: Bolt specification.
        preload: Preload calculation result (after all losses).
        stiffness: Stiffness calculation result.
        load_dist: Load distribution result (critical bolt loads).
        interface: Clamped interface definition.
        loading: External loading.
        plate_thickness: Thinnest plate for bearing check [mm].
        plate_yield_strength: Plate yield strength for bearing [MPa].
        standard: "VDI" or "ECSS" convention (labels; FoS passed explicitly).
        nut_factor_K: Nut factor for torsional stress terms (None → no
            tightening torsion, e.g. tensioner-tightened).
        fos_yield / fos_ultimate / fos_separation / fos_slip: Factors of
            safety per check family.
        surface_pressure_limit: p_G [MPa] or None (1.4·plate yield default).
        shear_plane_in_threads: Shear plane location for the shear checks.
        tapped_engagement_length: Engagement L_e [mm] for tapped joints
            (None = nut joint, stripping check skipped).
        tapped_material_uts: UTS of the tapped material [MPa].
        assembly_nu: Utilisation factor ν on σ_y for the assembly yield
            check (0.9 VDI, 1.0 ECSS).
        fos_yield_installation / fos_ultimate_installation: Installation
            factors of safety for the assembly checks.

    Returns:
        List of MarginOfSafety, sorted worst-first, with binding flag set.
    """
    F_ext = load_dist.F_total_axial   # Total external axial on critical bolt [N]
    F_ext_min = load_dist.F_total_axial_min
    V_shear = load_dist.V_shear_per_bolt

    margins: List[MarginOfSafety] = []

    # 1. Yield + ultimate at assembly (with tightening torsion)
    margins.append(check_yield_assembly(
        bolt, preload, nut_factor_K, assembly_nu, fos_yield_installation))
    margins.append(check_ultimate_assembly(
        bolt, preload, nut_factor_K, fos_ultimate_installation))

    # 2. Yield under working load
    margins.append(check_yield_combined(
        bolt, preload, stiffness, F_ext, nut_factor_K, fos_yield))

    # 3. Ultimate under working load
    margins.append(check_ultimate_combined(
        bolt, preload, stiffness, F_ext, nut_factor_K, fos_ultimate))

    # 4. Joint separation
    margins.append(check_joint_separation(
        preload, stiffness, F_ext, standard, fos_separation))

    # 5. Slip
    margins.append(check_slip(
        preload, F_ext, stiffness,
        interface.friction_coefficient,
        interface.num_friction_interfaces,
        V_shear,
        fos_slip,
    ))

    # 6. Bolt shear (yield + ultimate)
    margins.extend(check_bolt_shear(bolt, V_shear, shear_plane_in_threads, fos_ultimate))

    # 7. Bearing
    margins.append(check_bearing(bolt, V_shear, plate_thickness, plate_yield_strength))

    # 8. Surface pressure under head
    margins.append(check_surface_pressure(
        bolt, preload, stiffness, F_ext, surface_pressure_limit, plate_yield_strength))

    # 9. Fatigue
    margins.append(check_fatigue(bolt, preload, stiffness, F_ext, F_ext_min))

    # 10. Thread stripping (tapped joints only)
    if tapped_engagement_length is not None and tapped_material_uts is not None:
        F_bolt_max = preload.F_preload_max + stiffness.phi_n * max(0.0, F_ext)
        margins.append(check_thread_stripping(
            bolt, F_bolt_max, tapped_engagement_length, tapped_material_uts, fos_ultimate))

    # Sort worst-first; cap inf for comparison
    margins.sort(key=lambda m: m.value if m.value != float("inf") else 1e9)

    # Flag the binding constraint (lowest finite margin)
    finite = [m for m in margins if m.value != float("inf")]
    if finite:
        finite[0].binding = True

    return margins

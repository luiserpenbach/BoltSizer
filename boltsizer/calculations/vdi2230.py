"""VDI 2230 top-level analysis orchestrator.

Runs the full bolt sizing analysis per VDI 2230 Part 1 (2014) and
optionally ECSS-E-HB-32-23A conventions.

The analysis sequence is:
  R0  – Input validation
  R1  – Required minimum clamping force (separation/slip)
  R2  – Minimum assembly preload (derive from R1 or user-specified)
  R3  – Maximum assembly preload / assembly torque
  R4  – Bolt load under working conditions
  R5  – Separation check
  R6  – Yield checks (assembly + combined)
  R7  – Slip check
  R8  – Surface pressure check (if required)
  R9  – Fatigue check
  R10 – Tightening torque
  R11 – Compression check / bearing

References: VDI 2230 Part 1 (2014), §5.1–5.5.
"""
from __future__ import annotations
import math
from typing import List, Literal, Optional
from boltsizer.models.bolt import Bolt
from boltsizer.models.joint import BoltCircle, ClampedInterface, ExternalLoading
from boltsizer.models.results import (
    AnalysisResults, BoltResults, MarginOfSafety,
    PreloadResult, StiffnessResult, LoadDistributionResult,
)
from boltsizer.calculations.preload import calculate_preload
from boltsizer.calculations.joint_stiffness import calculate_joint_stiffness
from boltsizer.calculations.load_distribution import calculate_load_distribution
from boltsizer.calculations.failure_modes import calculate_all_margins


def _build_calc_steps(
    preload: PreloadResult,
    stiffness: StiffnessResult,
    load_dist: LoadDistributionResult,
    bolt: Bolt,
    loading: ExternalLoading,
    grip_length: float,
) -> List[dict]:
    """Build ordered calculation step records for UI display."""
    d = bolt.geometry.nominal_diameter
    A_s = bolt.geometry.stress_area
    K = None  # Will be filled by caller context

    steps = [
        {
            "step": "R1 — Preload from assembly torque",
            "formula_latex": r"F_M = \frac{M_A}{K \cdot d}",
            "substitution": f"Nominal preload = {preload.F_M_nominal:.1f} N",
            "result": f"F_M_max = {preload.F_M_max:.1f} N",
            "explanation": "The assembly torque is converted to bolt preload via the nut/K-factor.",
        },
        {
            "step": "R2 — Tightening scatter",
            "formula_latex": r"F_{M,\min} = \frac{F_{M,\max}}{\alpha_A}",
            "substitution": f"α_A = {preload.alpha_A:.2f}",
            "result": f"F_M_min = {preload.F_M_min:.1f} N",
            "explanation": "The scatter factor accounts for variation in achieved preload with the chosen tightening method.",
        },
        {
            "step": "R3 — Embedding relaxation",
            "formula_latex": r"F_Z = \frac{f_Z \cdot E_S \cdot A_S}{l_K}",
            "substitution": (
                f"f_Z = {preload.f_Z_displacement:.4f} mm, "
                f"E_S = {bolt.material.youngs_modulus:.0f} MPa, "
                f"A_s = {A_s:.1f} mm², l_K = {grip_length:.1f} mm"
            ),
            "result": f"F_Z = {preload.F_Z:.1f} N → F_V_min = {preload.F_preload_min:.1f} N",
            "explanation": "Embedding relaxation reduces the minimum preload as surface asperities flatten under load.",
        },
        {
            "step": "R4 — Bolt compliance δ_S",
            "formula_latex": r"\delta_S = \sum_i \frac{l_i}{E_S \cdot A_i}",
            "substitution": f"Shank + thread + head contributions",
            "result": f"δ_S = {stiffness.delta_S:.4e} mm/N",
            "explanation": "Bolt axial compliance determines how much of an external load increases the bolt force.",
        },
        {
            "step": "R5 — Clamped-part compliance δ_P",
            "formula_latex": r"\delta_P = \sum_{layers} \frac{f(l, d_w, d_h)}{E_P}",
            "substitution": "Rotscher pressure cone model (φ_K = 30°)",
            "result": f"δ_P = {stiffness.delta_P:.4e} mm/N",
            "explanation": "Clamped-part compliance via the Rotscher pressure cone governs how external loads split between bolt and joint.",
        },
        {
            "step": "R6 — Force ratio φ",
            "formula_latex": r"\varphi = \frac{\delta_P}{\delta_S + \delta_P}, \quad \varphi_n = n \cdot \varphi",
            "substitution": (
                f"n = {stiffness.load_intro_factor_n:.2f}, "
                f"δ_S = {stiffness.delta_S:.4e}, δ_P = {stiffness.delta_P:.4e}"
            ),
            "result": f"φ = {stiffness.phi_basic:.4f}, φ_n = {stiffness.phi_n:.4f}",
            "explanation": "φ_n is the fraction of external axial load that increases the bolt force (remainder reduces clamping).",
        },
        {
            "step": "R7 — Load distribution (bolt circle)",
            "formula_latex": (
                r"F_{B,i} = \frac{M_B \cdot r_i \cos\theta_i}{\sum r_j^2 \cos^2\theta_j}"
            ),
            "substitution": (
                f"F_axial/bolt = {load_dist.F_axial_per_bolt:.1f} N, "
                f"F_bending (crit.) = {load_dist.F_bend_per_bolt:.1f} N"
            ),
            "result": (
                f"Critical bolt #{load_dist.critical_bolt_index}: "
                f"F_total_axial = {load_dist.F_total_axial:.1f} N, "
                f"V_shear = {load_dist.V_shear_per_bolt:.1f} N"
            ),
            "explanation": "Bending moments are distributed among bolts proportional to their radial position.",
        },
    ]
    return steps


def _check_warnings(
    bolt: Bolt,
    preload: PreloadResult,
    margins: List[MarginOfSafety],
    loading: ExternalLoading,
) -> List[str]:
    """Generate engineering warning strings for the warnings panel."""
    warnings = []

    # Torque-to-yield proximity (ECSS: flag > 90% utilisation)
    A_s = bolt.geometry.stress_area
    sigma_proof = bolt.material.proof_load_stress or bolt.material.yield_strength
    utilisation = preload.F_M_max / (A_s * sigma_proof) * 100
    if utilisation > 90:
        warnings.append(
            f"⚠ Bolt utilisation at assembly is {utilisation:.1f}% of proof load. "
            "ECSS-E-HB-32-23A prohibits torque-to-yield tightening for space hardware. "
            "Consider reducing assembly torque or using a larger bolt."
        )

    # Embedding loss
    if preload.F_M_min > 0:
        embed_pct = (preload.F_Z / preload.F_M_min) * 100
        if embed_pct > 20:
            warnings.append(
                f"⚠ Embedding relaxation represents {embed_pct:.1f}% of minimum preload. "
                "Consider hydraulic tensioning or improved surface finish to reduce scatter."
            )

    # Slip check with friction-only (no physical shear prevention)
    slip_ms = next((m for m in margins if m.check_name == "Interface Slip"), None)
    if slip_ms and slip_ms.value < 0.5:
        warnings.append(
            "ℹ Slip margin is close to the limit. If shear is friction-reacted only, "
            "consider adding a shear pin or boss to physically prevent slip."
        )

    # Self-loosening risk (Junker criterion — simplified)
    # If shear force is significant relative to clamping, self-loosening risk exists
    if loading.shear_force > 0 and preload.F_preload_min > 0:
        shear_ratio = (loading.load_factor * loading.shear_force) / preload.F_preload_min
        if shear_ratio > 0.3:
            warnings.append(
                "⚠ Self-loosening risk: lateral loading is significant relative to preload. "
                "Recommend wire locking, prevailing-torque nut, or thread-lock compound "
                "per ECSS-E-HB-32-23A §8.6."
            )

    return warnings


def run_vdi2230_analysis(
    bolt_circle: BoltCircle,
    interface: ClampedInterface,
    load_cases: List[ExternalLoading],
    load_intro_factor_n: float = 0.5,
    plate_thickness: float = 10.0,
    plate_yield_strength: float = 240.0,
    standard: Literal["VDI", "ECSS"] = "VDI",
) -> AnalysisResults:
    """Run the full VDI 2230 bolt sizing analysis for all load cases.

    Args:
        bolt_circle: Bolt pattern and bolt specification.
        interface: Clamped stack definition.
        load_cases: List of ExternalLoading cases to check.
        load_intro_factor_n: Load introduction factor n ∈ [0, 1].
        plate_thickness: Thinnest plate for bearing check [mm].
        plate_yield_strength: Plate yield for bearing check [MPa].
        standard: "VDI" or "ECSS" convention.

    Returns:
        AnalysisResults with one BoltResults per load case.
    """
    grip_length = interface.total_clamped_length

    # --- Preload (same for all load cases) ---
    preload = calculate_preload(bolt_circle, grip_length)

    # --- Joint stiffness (same for all load cases) ---
    stiffness = calculate_joint_stiffness(bolt_circle, interface, load_intro_factor_n)

    bolt = bolt_circle.bolt
    case_results: List[BoltResults] = []

    for lc in load_cases:
        # --- Load distribution ---
        load_dist = calculate_load_distribution(bolt_circle, lc)

        F_ext = load_dist.F_total_axial
        V_shear = load_dist.V_shear_per_bolt

        # Maximum bolt load
        F_bolt_max = preload.F_M_max + stiffness.phi_n * max(0.0, F_ext)

        # Fatigue amplitude (half-range of bolt load variation)
        F_bolt_amplitude = stiffness.phi_n * abs(F_ext) / 2.0

        # Minimum clamping force on critical bolt
        F_clamp_min = max(0.0, preload.F_preload_min - max(0.0, F_ext) * (1.0 - stiffness.phi_n))

        # --- Failure mode margins ---
        margins = calculate_all_margins(
            bolt=bolt,
            preload=preload,
            stiffness=stiffness,
            load_dist=load_dist,
            interface=interface,
            loading=lc,
            plate_thickness=plate_thickness,
            plate_yield_strength=plate_yield_strength,
            standard=standard,
        )

        # --- Calculation steps for UI ---
        calc_steps = _build_calc_steps(preload, stiffness, load_dist, bolt, lc, grip_length)

        # --- Warnings ---
        warnings = _check_warnings(bolt, preload, margins, lc)

        case_results.append(BoltResults(
            case_name=lc.case_name,
            preload=preload,
            stiffness=stiffness,
            load_dist=load_dist,
            bolt_load_max=F_bolt_max,
            bolt_load_amplitude=F_bolt_amplitude,
            F_clamp_min=F_clamp_min,
            margins=margins,
            calc_steps=calc_steps,
            warnings=warnings,
        ))

    return AnalysisResults(standard=standard, case_results=case_results)

"""VDI 2230 top-level analysis orchestrator.

Runs the full bolt sizing analysis per VDI 2230 Part 1 (2014) with
optional ECSS-E-HB-32-23A conventions (factors of safety).

The analysis sequence is:
  1. Joint stiffness: δ_S, δ_P, φ, φ_n           (§5.1)
  2. Preload: torque → F_M_nom, scatter, embedding (§5.4)
  3. Per load case:
       - thermal preload change (CTE mismatch)
       - load distribution over the bolt circle
       - per-case load-introduction factor n (load_plane)
       - all failure-mode margins
"""
from __future__ import annotations
import math
from dataclasses import replace
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
from boltsizer.ecss.ecss_hb_32_23 import get_default_fos
from boltsizer.standards.material_library import get_flange_cte

_DEFAULT_BOLT_CTE = 11.5e-6  # [1/K] steel fallback


def _thermal_preload_delta(
    bolt: Bolt,
    interface: ClampedInterface,
    total_compliance: float,
    delta_T: float,
) -> float:
    """Thermal preload CHANGE [N]; positive = preload LOSS.

    ΔF_th = ΔT·(α_S·l_K − Σ α_i·t_i) / (δ_S + δ_P)

    The bolt expanding more than the clamped stack (α_S·l_K > Σα_i·t_i at
    ΔT > 0) relaxes the joint.  Stiffness change with temperature is
    neglected (small for moderate ΔT).
    """
    if delta_T == 0.0 or total_compliance <= 0:
        return 0.0
    l_K = interface.total_clamped_length
    alpha_S = bolt.material.cte if bolt.material.cte is not None else _DEFAULT_BOLT_CTE
    stack_expansion = 0.0
    for layer in interface.layers:
        cte = layer.cte if layer.cte is not None else get_flange_cte(layer.material)
        stack_expansion += cte * layer.thickness
    return delta_T * (alpha_S * l_K - stack_expansion) / total_compliance


def _apply_thermal(preload: PreloadResult, F_th: float) -> PreloadResult:
    """Return a per-case PreloadResult with the thermal change applied.

    Positive F_th (loss) reduces the minimum preload; negative F_th
    (gain, e.g. cold case with high-CTE flanges) increases the maximum
    preload.  Both directions are applied to the conservative bound only.
    """
    if F_th == 0.0:
        return preload
    F_preload_min = max(0.0, preload.F_preload_min - max(0.0, F_th))
    F_preload_max = preload.F_preload_max + max(0.0, -F_th)
    return replace(
        preload,
        F_preload_min=F_preload_min,
        F_preload_max=F_preload_max,
    )


def _build_calc_steps(
    preload: PreloadResult,
    stiffness: StiffnessResult,
    load_dist: LoadDistributionResult,
    bolt: Bolt,
    loading: ExternalLoading,
    grip_length: float,
    F_th: float,
    torque_mode: bool,
) -> List[dict]:
    """Build ordered calculation step records for UI display."""
    A_s = bolt.geometry.stress_area

    preload_step = {
        "step": "R1 — Assembly preload",
        "formula_latex": (
            r"F_{M,nom} = \frac{M_A}{K \cdot d}" if torque_mode
            else r"F_{M,nom} = F_{target}"
        ),
        "substitution": f"Nominal preload = {preload.F_M_nominal:.1f} N",
        "result": f"F_M_nom = {preload.F_M_nominal:.1f} N",
        "explanation": (
            "The assembly torque is converted to bolt preload via the nut/K-factor."
            if torque_mode else
            "Direct target preload specified (no torque conversion)."
        ),
    }

    steps = [
        {
            "step": "R2 — Bolt compliance δ_S",
            "formula_latex": (
                r"\delta_S = \frac{0.4d}{EA_N} + \frac{l_1}{EA_N}"
                r" + \frac{l_{Gew}}{EA_{d3}} + \frac{0.5d}{EA_{d3}} + \frac{0.4d}{EA_N}"
            ),
            "substitution": "Head + shank + thread + engaged + nut contributions (VDI 2230 §5.1.1)",
            "result": f"δ_S = {stiffness.delta_S:.4e} mm/N",
            "explanation": "Bolt axial compliance determines how much of an external load increases the bolt force.",
        },
        {
            "step": "R3 — Clamped-part compliance δ_P",
            "formula_latex": (
                r"\delta_P = \sum \frac{1}{\pi E d_h \tan\varphi_K}"
                r"\ln\!\left(\frac{(D_2-d_h)(D_1+d_h)}{(D_2+d_h)(D_1-d_h)}\right)"
            ),
            "substitution": "Compression-cone model, opposed cones meeting at mid-grip",
            "result": f"δ_P = {stiffness.delta_P:.4e} mm/N",
            "explanation": "Clamped-part compliance governs how external loads split between bolt and joint.",
        },
        {
            "step": "R4 — Force ratio φ",
            "formula_latex": r"\varphi = \frac{\delta_P}{\delta_S + \delta_P}, \quad \varphi_n = n \cdot \varphi",
            "substitution": (
                f"n = {stiffness.load_intro_factor_n:.2f}, "
                f"δ_S = {stiffness.delta_S:.4e}, δ_P = {stiffness.delta_P:.4e}"
            ),
            "result": f"φ = {stiffness.phi_basic:.4f}, φ_n = {stiffness.phi_n:.4f}",
            "explanation": "φ_n is the fraction of external axial load that increases the bolt force (remainder reduces clamping).",
        },
        preload_step,
        {
            "step": "R5 — Tightening scatter",
            "formula_latex": (
                r"F_{M,\max/\min} = F_{M,nom}(1 \pm \varepsilon),\ "
                r"\varepsilon = \frac{\alpha_A - 1}{\alpha_A + 1}"
            ),
            "substitution": f"α_A = {preload.alpha_A:.2f}",
            "result": f"F_M_max = {preload.F_M_max:.1f} N, F_M_min = {preload.F_M_min:.1f} N",
            "explanation": "Symmetric preload scatter about the nominal for the chosen tightening method (F_M_max/F_M_min = α_A).",
        },
        {
            "step": "R6 — Embedding relaxation",
            "formula_latex": r"F_Z = \frac{f_Z}{\delta_S + \delta_P}",
            "substitution": (
                f"f_Z = {preload.f_Z_displacement * 1000:.1f} μm, "
                f"δ_S+δ_P = {stiffness.delta_S + stiffness.delta_P:.4e} mm/N"
            ),
            "result": f"F_Z = {preload.F_Z:.1f} N → F_V_min = {preload.F_preload_min:.1f} N",
            "explanation": "Embedding relaxation reduces the minimum preload as surface asperities flatten under load.",
        },
    ]
    if F_th != 0.0:
        steps.append({
            "step": "R7 — Thermal preload change",
            "formula_latex": r"\Delta F_{th} = \frac{\Delta T (\alpha_S l_K - \sum \alpha_i t_i)}{\delta_S + \delta_P}",
            "substitution": f"ΔT = {loading.delta_T:.1f} K",
            "result": f"ΔF_th = {F_th:+.1f} N ({'loss' if F_th > 0 else 'gain'})",
            "explanation": "CTE mismatch between bolt and clamped stack changes the preload with temperature.",
        })
    steps.append({
        "step": "R8 — Load distribution (bolt circle)",
        "formula_latex": (
            r"F_{B,i} = \frac{M_B \cdot r_i \cos\theta_i}{\sum r_j^2 \cos^2\theta_j},\ "
            r"V_i = \frac{V}{n_B} + \frac{M_T}{n_B r}"
        ),
        "substitution": (
            f"F_axial/bolt = {load_dist.F_axial_per_bolt:.1f} N, "
            f"F_bending (crit.) = {load_dist.F_bend_per_bolt:.1f} N, "
            f"V_torsion = {load_dist.V_torsion_per_bolt:.1f} N"
        ),
        "result": (
            f"Critical bolt #{load_dist.critical_bolt_index}: "
            f"F_total_axial = {load_dist.F_total_axial:.1f} N, "
            f"V_shear = {load_dist.V_shear_per_bolt:.1f} N"
        ),
        "explanation": "Bending moments are distributed among bolts proportional to their radial position; torsion adds tangential shear.",
    })
    return steps


def _check_warnings(
    bolt: Bolt,
    bolt_circle: BoltCircle,
    interface: ClampedInterface,
    preload: PreloadResult,
    margins: List[MarginOfSafety],
    load_dist: LoadDistributionResult,
    loading: ExternalLoading,
) -> List[str]:
    """Generate engineering warning strings for the warnings panel."""
    warnings = []

    # Torque-to-yield proximity (ECSS: flag > 90% utilisation)
    A_s = bolt.geometry.stress_area
    sigma_proof = bolt.material.proof_load_stress or bolt.material.yield_strength
    utilisation = preload.F_M_max / (A_s * sigma_proof) * 100 if sigma_proof > 0 else 0.0
    if utilisation > 90:
        warnings.append(
            f"⚠ Bolt utilisation at assembly is {utilisation:.1f}% of proof load. "
            "ECSS-E-HB-32-23A prohibits torque-to-yield tightening for space hardware. "
            "Consider reducing assembly torque or using a larger bolt."
        )

    # Shank/thread inputs vs grip consistency
    l_K = interface.total_clamped_length
    if bolt.geometry.shank_length > l_K:
        warnings.append(
            f"⚠ Shank length ({bolt.geometry.shank_length:.1f} mm) exceeds the grip "
            f"length ({l_K:.1f} mm); the shank was truncated to the grip for the "
            "compliance calculation. Check the bolt geometry inputs."
        )

    # Embedding loss
    if preload.F_M_min > 0:
        embed_pct = (preload.F_Z / preload.F_M_min) * 100
        if embed_pct > 20:
            warnings.append(
                f"⚠ Embedding relaxation represents {embed_pct:.1f}% of minimum preload. "
                "Consider elongation-controlled tightening or improved surface finish."
            )

    # Slip check with friction-only (no physical shear prevention)
    slip_ms = next((m for m in margins if m.check_name == "Interface Slip"), None)
    if slip_ms and slip_ms.value < 0.5:
        warnings.append(
            "ℹ Slip margin is close to the limit. If shear is friction-reacted only, "
            "consider adding a shear pin or boss to physically prevent slip."
        )

    # Torsion on a degenerate pattern cannot be reacted by bolt shear
    if loading.torsion != 0.0 and load_dist.V_torsion_per_bolt == 0.0:
        warnings.append(
            "⚠ A torsion moment was specified but the bolt pattern has no radius "
            "to react it (single bolt / zero PCD). The torsion was NOT included "
            "in the bolt shear loads — verify the torsion load path."
        )

    # Self-loosening risk (Junker criterion — simplified, per-bolt basis)
    V_per_bolt = abs(load_dist.V_shear_per_bolt)
    if V_per_bolt > 0 and preload.F_preload_min > 0:
        shear_ratio = V_per_bolt / preload.F_preload_min
        if shear_ratio > 0.3:
            warnings.append(
                "⚠ Self-loosening risk: lateral load per bolt is significant relative "
                "to its preload. Recommend wire locking, prevailing-torque nut, or "
                "thread-lock compound per ECSS-E-HB-32-23A §8.6."
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
    fos_yield: Optional[float] = None,
    fos_ultimate: Optional[float] = None,
    fos_separation: Optional[float] = None,
    fos_slip: Optional[float] = None,
    surface_pressure_limit: Optional[float] = None,
    shear_plane_in_threads: bool = True,
    tapped_engagement_length: Optional[float] = None,
    tapped_material_uts: Optional[float] = None,
    fos_yield_installation: float = 1.0,
    fos_ultimate_installation: float = 1.0,
) -> AnalysisResults:
    """Run the full VDI 2230 bolt sizing analysis for all load cases.

    Args:
        bolt_circle: Bolt pattern and bolt specification.
        interface: Clamped stack definition.
        load_cases: List of ExternalLoading cases to check.
        load_intro_factor_n: Load introduction factor n ∈ [0, 1]
            (per-case override to n = 1 when load_plane == "bolt_head").
        plate_thickness: Thinnest plate for bearing check [mm].
        plate_yield_strength: Plate yield for bearing check [MPa].
        standard: "VDI" or "ECSS" convention — sets default FoS values.
        fos_yield / fos_ultimate / fos_separation / fos_slip: Explicit
            factors of safety; None → defaults for the chosen standard
            (ECSS: 1.1 / 1.25 / 1.2 / 1.0, VDI: all 1.0).
        surface_pressure_limit: p_G [MPa] for the head bearing check
            (None → 1.4·plate yield).
        shear_plane_in_threads: Shear plane location for shear checks.
        tapped_engagement_length: Engagement L_e [mm] for tapped joints.
        tapped_material_uts: UTS of tapped material [MPa].
        fos_yield_installation / fos_ultimate_installation: Installation
            factors of safety for the assembly checks (default 1.0).

    Returns:
        AnalysisResults with one BoltResults per load case.
    """
    grip_length = interface.total_clamped_length
    bolt = bolt_circle.bolt

    # --- Factors of safety (defaults by standard) ---
    fos_defaults = get_default_fos(standard)
    fos_y = fos_yield if fos_yield is not None else fos_defaults["yield"]
    fos_u = fos_ultimate if fos_ultimate is not None else fos_defaults["ultimate"]
    fos_sep = fos_separation if fos_separation is not None else fos_defaults["separation"]
    fos_sl = fos_slip if fos_slip is not None else fos_defaults["slip"]

    # --- Joint stiffness (same for all load cases) ---
    stiffness = calculate_joint_stiffness(bolt_circle, interface, load_intro_factor_n)
    total_compliance = stiffness.delta_S + stiffness.delta_P

    # --- Preload (same for all load cases; embedding uses joint stiffness) ---
    any_shear = any(
        (lc.shear_force != 0.0 or lc.torsion != 0.0) for lc in load_cases
    )
    preload = calculate_preload(
        bolt_circle,
        grip_length,
        total_compliance=total_compliance,
        num_inner_interfaces=max(0, len(interface.layers) - 1),
        embedding_loading_type="shear" if any_shear else "axial",
    )

    torque_mode = bolt_circle.assembly_torque > 0
    if torque_mode:
        # Pair the assembly torsion with the friction state that produces
        # the maximum preload: K_min when a friction range is given (the
        # physically consistent worst pairing), else nominal K.
        nut_factor_for_torsion = (
            bolt_circle.nut_factor_K_min
            if bolt_circle.nut_factor_K_min
            else bolt_circle.nut_factor_K
        )
    else:
        nut_factor_for_torsion = None

    # Assembly-check convention: VDI uses ν = 0.9 on σ_y; ECSS uses the
    # full σ_y with explicit installation factors of safety.
    assembly_nu = 1.0 if standard == "ECSS" else 0.9

    case_results: List[BoltResults] = []

    for lc in load_cases:
        # --- Per-case load introduction factor ---
        n_case = 1.0 if lc.load_plane == "bolt_head" else load_intro_factor_n
        if n_case != stiffness.load_intro_factor_n:
            stiffness_case = replace(
                stiffness,
                phi_n=n_case * stiffness.phi_basic,
                load_intro_factor_n=n_case,
            )
        else:
            stiffness_case = stiffness

        # --- Thermal preload change for this case ---
        F_th = _thermal_preload_delta(bolt, interface, total_compliance, lc.delta_T)
        preload_case = _apply_thermal(preload, F_th)

        # --- Load distribution ---
        load_dist = calculate_load_distribution(bolt_circle, lc)

        F_ext = load_dist.F_total_axial
        F_ext_min = load_dist.F_total_axial_min

        # Maximum bolt load
        F_bolt_max = preload_case.F_preload_max + stiffness_case.phi_n * max(0.0, F_ext)

        # Fatigue amplitude (half-range of bolt load variation)
        F_bolt_amplitude = abs(stiffness_case.phi_n * (F_ext - F_ext_min) / 2.0)

        # Minimum clamping force on critical bolt
        F_clamp_min = max(
            0.0,
            preload_case.F_preload_min - max(0.0, F_ext) * (1.0 - stiffness_case.phi_n),
        )

        # --- Failure mode margins ---
        margins = calculate_all_margins(
            bolt=bolt,
            preload=preload_case,
            stiffness=stiffness_case,
            load_dist=load_dist,
            interface=interface,
            loading=lc,
            plate_thickness=plate_thickness,
            plate_yield_strength=plate_yield_strength,
            standard=standard,
            nut_factor_K=nut_factor_for_torsion,
            fos_yield=fos_y,
            fos_ultimate=fos_u,
            fos_separation=fos_sep,
            fos_slip=fos_sl,
            surface_pressure_limit=surface_pressure_limit,
            shear_plane_in_threads=shear_plane_in_threads,
            tapped_engagement_length=tapped_engagement_length,
            tapped_material_uts=tapped_material_uts,
            assembly_nu=assembly_nu,
            fos_yield_installation=fos_yield_installation,
            fos_ultimate_installation=fos_ultimate_installation,
        )

        # --- Calculation steps for UI ---
        calc_steps = _build_calc_steps(
            preload_case, stiffness_case, load_dist, bolt, lc, grip_length, F_th, torque_mode,
        )

        # --- Warnings ---
        warnings = _check_warnings(
            bolt, bolt_circle, interface, preload_case, margins, load_dist, lc,
        )

        case_results.append(BoltResults(
            case_name=lc.case_name,
            preload=preload_case,
            stiffness=stiffness_case,
            load_dist=load_dist,
            bolt_load_max=F_bolt_max,
            bolt_load_amplitude=F_bolt_amplitude,
            F_clamp_min=F_clamp_min,
            F_thermal_delta=F_th,
            margins=margins,
            calc_steps=calc_steps,
            warnings=warnings,
        ))

    return AnalysisResults(standard=standard, case_results=case_results)

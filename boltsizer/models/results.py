"""Calculation result data models.

All values in SI units: N, mm, MPa.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal


@dataclass
class MarginOfSafety:
    """Single margin of safety for one failure mode.

    MS = (allowable / applied) - 1
    Positive MS → PASS, negative → FAIL.

    Attributes:
        check_name: Human-readable name, e.g. "Yield at Assembly".
        value: Margin of safety value (dimensionless).
        status: "PASS", "FAIL", or "WARNING".
        binding: True if this is the worst (lowest) margin in the set.
        allowable: Allowable value (in check units).
        applied: Applied value (in check units).
        unit: Unit string for allowable/applied display.
        explanation: One-sentence plain-English explanation of the result.
        formula_latex: LaTeX string for the check formula (for UI display).
    """
    check_name: str
    value: float
    status: Literal["PASS", "FAIL", "WARNING"]
    binding: bool
    allowable: float
    applied: float
    unit: str
    explanation: str
    formula_latex: str = ""


@dataclass
class PreloadResult:
    """Preload calculation outputs.

    Attributes:
        F_M_nominal: Nominal (mean) assembly preload [N].
        F_M_max: Maximum assembly preload [N] (after scatter).
        F_M_min: Minimum assembly preload after scatter [N].
        F_Z: Embedding relaxation force [N].
        F_preload_max: Maximum preload after embedding [N] = F_M_max (embedding doesn't increase).
        F_preload_min: Minimum preload after embedding [N] = F_M_min - F_Z.
        alpha_A: Tightening scatter factor (F_max / F_min).
        f_Z_displacement: Embedding displacement [mm].
    """
    F_M_nominal: float
    F_M_max: float
    F_M_min: float
    F_Z: float
    F_preload_max: float
    F_preload_min: float
    alpha_A: float
    f_Z_displacement: float


@dataclass
class StiffnessResult:
    """Joint stiffness calculation outputs (VDI 2230 §5.1–5.3).

    Attributes:
        delta_S: Bolt compliance [mm/N].
        delta_P: Clamped-part compliance [mm/N].
        phi_basic: Basic force ratio φ = δ_P / (δ_S + δ_P).
        phi_n: Load-introduction-corrected force ratio φ_n = n · φ.
        load_intro_factor_n: Load introduction factor n.
    """
    delta_S: float              # [mm/N] bolt compliance
    delta_P: float              # [mm/N] clamped-part compliance
    phi_basic: float            # force ratio
    phi_n: float                # corrected force ratio
    load_intro_factor_n: float


@dataclass
class LoadDistributionResult:
    """Per-bolt load distribution result.

    Attributes:
        critical_bolt_index: Index (0-based) of the most loaded bolt.
        F_axial_per_bolt: Axial force on critical bolt [N] (tension +).
        F_bend_per_bolt: Additional axial force due to bending on critical bolt [N].
        V_shear_per_bolt: Shear force on critical bolt [N].
        F_total_axial: Total axial load on critical bolt [N] = F_axial + F_bend.
        bolt_angles_deg: Angle of each bolt from reference [deg].
        bolt_axial_forces: Axial force on every bolt [N] (list).
    """
    critical_bolt_index: int
    F_axial_per_bolt: float
    F_bend_per_bolt: float
    V_shear_per_bolt: float
    F_total_axial: float
    bolt_angles_deg: List[float]
    bolt_axial_forces: List[float]


@dataclass
class BoltResults:
    """Complete results for a single load case.

    Attributes:
        case_name: Load case identifier.
        preload: Preload calculation results.
        stiffness: Stiffness calculation results.
        load_dist: Load distribution results.
        bolt_load_max: Maximum total bolt load [N].
        bolt_load_amplitude: Fatigue load amplitude [N].
        F_clamp_min: Minimum clamping force per bolt at critical bolt [N].
        margins: List of all margin of safety checks.
        calc_steps: Ordered list of calculation step dicts for UI display.
                    Each dict: {step, formula_latex, substitution, result, explanation}.
        warnings: List of warning strings.
    """
    case_name: str
    preload: PreloadResult
    stiffness: StiffnessResult
    load_dist: LoadDistributionResult
    bolt_load_max: float
    bolt_load_amplitude: float
    F_clamp_min: float
    margins: List[MarginOfSafety]
    calc_steps: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def binding_margin(self) -> Optional[MarginOfSafety]:
        """Return the binding (lowest) margin of safety."""
        if not self.margins:
            return None
        return min(self.margins, key=lambda m: m.value)


@dataclass
class AnalysisResults:
    """Top-level analysis result containing all load cases.

    Attributes:
        standard: "VDI" or "ECSS" — controls which convention applies.
        case_results: List of BoltResults, one per load case.
    """
    standard: Literal["VDI", "ECSS"]
    case_results: List[BoltResults]

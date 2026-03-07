"""Joint stiffness calculation — VDI 2230 Part 1 (2014) §5.1–5.3.

Computes bolt compliance δ_S and clamped-part compliance δ_P using the
Rotscher pressure cone model, then derives the force ratio Phi (φ).

Reference equations:
  VDI 2230 (2014) §5.1:  Bolt compliance δ_S = Σ(l_i / (E_S · A_i))
  VDI 2230 (2014) §5.2:  Clamped-part compliance via Rotscher cone
  VDI 2230 (2014) §5.3:  φ = δ_P / (δ_S + δ_P)
                          φ_n = n · φ

Units: N (force), mm (length), MPa (stress = N/mm²), mm/N (compliance).
"""
from __future__ import annotations
import math
from typing import List
from boltsizer.models.bolt import Bolt
from boltsizer.models.joint import BoltCircle, ClampedInterface, ClampedLayer
from boltsizer.models.results import StiffnessResult

# ---------------------------------------------------------------------------
# LaTeX formula strings
# ---------------------------------------------------------------------------
FORMULA_BOLT_COMPLIANCE = r"\delta_S = \sum_i \frac{l_i}{E_S \cdot A_i}"
FORMULA_CONE_COMPLIANCE = (
    r"\delta_P = \frac{1}{E_P} \cdot \frac{1}{\pi \tan\phi_K}"
    r"\ln\!\left(\frac{(d_w + l_K \tan\phi_K - d_h)(d_w + d_h)}"
    r"{(d_w - d_h)(d_w + l_K \tan\phi_K + d_h)}\right)"
)
FORMULA_FORCE_RATIO = r"\varphi = \frac{\delta_P}{\delta_S + \delta_P}"
FORMULA_PHI_N = r"\varphi_n = n \cdot \varphi"

# Rotscher cone half-angle (VDI 2230 default)
_CONE_HALF_ANGLE_DEG = 30.0
_TAN_PHI_K = math.tan(math.radians(_CONE_HALF_ANGLE_DEG))


def _bolt_compliance(bolt: Bolt, grip_length: float) -> float:
    """Calculate bolt axial compliance δ_S [mm/N].

    The bolt compliance is the sum of compliances of:
      1. Unthreaded shank (diameter = nominal d, area = π·d²/4)
      2. Threaded section (area = stress area A_s)
      3. Head engagement (≈ 0.4·d length, area = A_s) — VDI 2230 §5.1 Annex

    VDI 2230 (2014) §5.1:  δ_S = Σ(l_i / (E_S · A_i))

    Args:
        bolt: Bolt specification.
        grip_length: Total clamped length l_K [mm].

    Returns:
        Compliance δ_S [mm/N].
    """
    geom = bolt.geometry
    mat = bolt.material
    E = mat.youngs_modulus  # [MPa]

    d = geom.nominal_diameter
    A_shank = math.pi / 4 * d ** 2     # Unthreaded shank area [mm²]
    A_s = geom.stress_area              # Threaded section area [mm²]

    l_shank = geom.shank_length
    l_thread = geom.threaded_length
    l_head = 0.4 * d                    # Head contribution (VDI 2230 §5.1)

    # Clamp to sensible values
    l_shank = max(0.0, l_shank)
    l_thread = max(0.0, l_thread)

    delta_shank = l_shank / (E * A_shank) if A_shank > 0 else 0.0
    delta_thread = l_thread / (E * A_s) if A_s > 0 else 0.0
    delta_head = l_head / (E * A_s) if A_s > 0 else 0.0

    return delta_shank + delta_thread + delta_head


def _clamped_part_compliance_rotscher(
    layers: List[ClampedLayer],
    d_w: float,
    d_h: float,
) -> float:
    """Calculate clamped-part compliance δ_P [mm/N] via Rotscher pressure cone.

    Uses the half-angle φ_K = 30° (VDI 2230 default).
    Each layer is treated as an independent cone frustum.

    For a single homogeneous layer:
        δ_P_layer = 1/(E_P · π · tan(φ_K)) ·
                    ln( (d_w + l · tan(φ_K) - d_h)(d_w + d_h) /
                        (d_w - d_h)(d_w + l · tan(φ_K) + d_h) )

    VDI 2230 (2014) §5.2, Eq. (5.4).

    Args:
        layers: List of clamped layers with material and thickness.
        d_w: Bearing (washer) face diameter [mm] ≈ head diameter.
        d_h: Hole diameter [mm] (nominal bolt diameter).

    Returns:
        Total compliance δ_P [mm/N].
    """
    delta_P = 0.0
    for layer in layers:
        l = layer.thickness
        E = layer.youngs_modulus
        if E <= 0 or l <= 0:
            continue

        # Guard: d_w must be > d_h
        if d_w <= d_h:
            # Fallback to simple cylindrical model if geometry degenerate
            A_eff = math.pi / 4 * (d_w ** 2 - d_h ** 2)
            A_eff = max(A_eff, 1.0)
            delta_P += l / (E * A_eff)
            continue

        tan_phi = _TAN_PHI_K
        # Rotscher formula
        num = (d_w + l * tan_phi - d_h) * (d_w + d_h)
        den = (d_w - d_h) * (d_w + l * tan_phi + d_h)
        if num <= 0 or den <= 0 or num / den <= 0:
            # Fallback
            A_eff = math.pi / 4 * (d_w ** 2 - d_h ** 2)
            A_eff = max(A_eff, 1.0)
            delta_P += l / (E * A_eff)
            continue

        delta_layer = math.log(num / den) / (E * math.pi * tan_phi)
        delta_P += delta_layer

    return delta_P


def calculate_joint_stiffness(
    bolt_circle: BoltCircle,
    interface: ClampedInterface,
    load_intro_factor_n: float = 0.5,
) -> StiffnessResult:
    """Calculate bolt and clamped-part compliance and force ratio.

    VDI 2230 (2014) §5.1–5.3.

    Steps:
      1. Bolt compliance δ_S (sum of shank + thread + head contributions).
      2. Clamped-part compliance δ_P via Rotscher pressure cone model.
      3. Basic force ratio φ = δ_P / (δ_S + δ_P).
      4. Load-corrected force ratio φ_n = n · φ.

    Args:
        bolt_circle: Bolt and tightening specification.
        interface: Clamped stack definition with layers.
        load_intro_factor_n: Load introduction factor n ∈ [0, 1].
            0 = load at interface (most conservative for bolt).
            1 = load at bolt head/nut (bolt sees full external load).

    Returns:
        StiffnessResult with δ_S, δ_P, φ, φ_n, n.
    """
    bolt = bolt_circle.bolt
    d = bolt.geometry.nominal_diameter

    # --- Step 1: Bolt compliance ---
    delta_S = _bolt_compliance(bolt, interface.total_clamped_length)

    # Bearing face diameter d_w ≈ 1.5·d (ISO hex head)
    d_w = 1.5 * d
    d_h = d  # Clearance hole ≈ d (tight-clearance assumption)

    # --- Step 2: Clamped-part compliance ---
    delta_P = _clamped_part_compliance_rotscher(
        interface.layers, d_w, d_h
    )

    # Protect against degenerate case
    total_compliance = delta_S + delta_P
    if total_compliance <= 0:
        phi_basic = 0.5  # Fallback
    else:
        # --- Step 3: Force ratio φ ---
        # VDI 2230 (2014) §5.3
        phi_basic = delta_P / total_compliance

    # --- Step 4: Load-corrected force ratio φ_n ---
    # VDI 2230 (2014) §5.3:  φ_n = n · φ
    phi_n = load_intro_factor_n * phi_basic

    return StiffnessResult(
        delta_S=delta_S,
        delta_P=delta_P,
        phi_basic=phi_basic,
        phi_n=phi_n,
        load_intro_factor_n=load_intro_factor_n,
    )

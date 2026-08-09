"""Joint stiffness calculation — VDI 2230 Part 1 (2014) §5.1.

Computes bolt compliance δ_S and clamped-part compliance δ_P, then derives
the force ratio Phi (φ).

Bolt compliance (VDI 2230 §5.1.1):
    δ_S = δ_head + δ_shank + δ_free_thread + δ_engaged_thread + δ_nut
        = 0.4·d/(E·A_N) + l_1/(E·A_N) + l_Gew/(E·A_d3)
          + 0.5·d/(E·A_d3) + 0.4·d/(E·A_N)
where A_N = π/4·d² (nominal area) and A_d3 = π/4·d3² (minor area).
The loaded lengths are reconciled with the grip: l_1 = min(shank, l_K),
l_Gew = l_K − l_1 (free loaded thread inside the grip).

Clamped-part compliance: compression-cone (frustum) model with half-angle
φ_K (default 30°).  Two opposed cones grow from the head and nut bearing
faces and meet at mid-grip.  Each axial slice through a layer contributes

    δ_slice = ln( ((D₂−d_h)(D₁+d_h)) / ((D₂+d_h)(D₁−d_h)) )
              / (π · E · d_h · tanφ_K)

which is the closed-form integral of dz/(E·A(z)) with
A(z) = π/4·(D(z)² − d_h²) and D(z) growing linearly at 2·tanφ_K per unit
depth from the nearest bearing face (equivalent to the Shigley §8-5
frustum formula; VDI 2230 §5.1.2 substitution-area form gives closely
similar results for common proportions).  Where the cone diameter reaches
the available flange diameter D_A, the section continues as a cylinder
with A = π/4·(D_A² − d_h²).

Force ratio (VDI 2230 §5.1.3 / §5.3):
    φ = δ_P / (δ_S + δ_P),   φ_n = n · φ

Units: N (force), mm (length), MPa (stress = N/mm²), mm/N (compliance).
"""
from __future__ import annotations
import math
from typing import List, Optional, Tuple
from boltsizer.models.bolt import Bolt
from boltsizer.models.joint import BoltCircle, ClampedInterface, ClampedLayer
from boltsizer.models.results import StiffnessResult

# ---------------------------------------------------------------------------
# LaTeX formula strings
# ---------------------------------------------------------------------------
FORMULA_BOLT_COMPLIANCE = (
    r"\delta_S = \frac{0.4d}{E A_N} + \frac{l_1}{E A_N}"
    r" + \frac{l_{Gew}}{E A_{d3}} + \frac{0.5d}{E A_{d3}} + \frac{0.4d}{E A_N}"
)
FORMULA_CONE_COMPLIANCE = (
    r"\delta_P = \sum \frac{1}{\pi E d_h \tan\varphi_K}"
    r"\ln\!\left(\frac{(D_2 - d_h)(D_1 + d_h)}{(D_2 + d_h)(D_1 - d_h)}\right)"
)
FORMULA_FORCE_RATIO = r"\varphi = \frac{\delta_P}{\delta_S + \delta_P}"
FORMULA_PHI_N = r"\varphi_n = n \cdot \varphi"


def _bolt_compliance(bolt: Bolt, grip_length: float) -> float:
    """Calculate bolt axial compliance δ_S [mm/N] per VDI 2230 §5.1.1.

    Elements in series:
      1. Head:            l = 0.4·d, area A_N
      2. Shank in grip:   l = min(shank_length, l_K), area A_N
      3. Free loaded thread in grip: l = l_K − shank-in-grip, area A_d3
      4. Engaged thread:  l = 0.5·d, area A_d3
      5. Nut / engaged internal thread region: l = 0.4·d, area A_N

    The loaded lengths are reconciled with the grip length so δ_S and δ_P
    always describe the same joint (the raw shank/threaded length inputs
    are only used to decide how much of the grip is shank vs thread).

    Args:
        bolt: Bolt specification.
        grip_length: Total clamped length l_K [mm].

    Returns:
        Compliance δ_S [mm/N].
    """
    geom = bolt.geometry
    E = bolt.material.youngs_modulus  # [MPa]

    d = geom.nominal_diameter
    A_N = geom.nominal_area
    A_d3 = geom.minor_area

    l_K = max(0.0, grip_length)
    l_shank = min(max(0.0, geom.shank_length), l_K)
    l_free_thread = l_K - l_shank

    delta_head = 0.4 * d / (E * A_N)
    delta_shank = l_shank / (E * A_N)
    delta_thread = l_free_thread / (E * A_d3)
    delta_engaged = 0.5 * d / (E * A_d3)
    delta_nut = 0.4 * d / (E * A_N)

    return delta_head + delta_shank + delta_thread + delta_engaged + delta_nut


def _frustum_slice_compliance(
    z1: float,
    z2: float,
    E: float,
    d_w: float,
    d_h: float,
    tan_phi: float,
    D_A: Optional[float],
) -> float:
    """Compliance of the cone slice between depths z1..z2 from a bearing face.

    The cone diameter at depth z from the bearing face is
    D(z) = d_w + 2·z·tanφ, capped at D_A (cylinder beyond that point).

    Args:
        z1, z2: Slice bounds as depth from the bearing face [mm], z2 > z1.
        E: Layer Young's modulus [MPa].
        d_w: Bearing face diameter [mm].
        d_h: Hole diameter [mm].
        tan_phi: tan of cone half-angle.
        D_A: Available (limiting) diameter [mm] or None.

    Returns:
        Compliance of the slice [mm/N].
    """
    if z2 <= z1 or E <= 0:
        return 0.0

    def cone_part(a: float, b: float) -> float:
        """Closed-form cone compliance from depth a to b (D < D_A region)."""
        D1 = d_w + 2.0 * a * tan_phi
        D2 = d_w + 2.0 * b * tan_phi
        num = (D2 - d_h) * (D1 + d_h)
        den = (D2 + d_h) * (D1 - d_h)
        if num <= 0 or den <= 0:
            return 0.0
        return math.log(num / den) / (math.pi * E * d_h * tan_phi)

    def cylinder_part(a: float, b: float, D: float) -> float:
        A = math.pi / 4.0 * (D ** 2 - d_h ** 2)
        if A <= 0:
            return 0.0
        return (b - a) / (E * A)

    if D_A is None or D_A <= d_w:
        if D_A is not None and D_A <= d_w:
            # Entire section is already at/above the limiting diameter:
            # treat as cylinder of D_A (degenerate narrow flange).
            D_cyl = max(D_A, d_h * 1.001)
            return cylinder_part(z1, z2, D_cyl)
        return cone_part(z1, z2)

    # Depth at which cone reaches D_A
    z_cap = (D_A - d_w) / (2.0 * tan_phi)
    if z2 <= z_cap:
        return cone_part(z1, z2)
    if z1 >= z_cap:
        return cylinder_part(z1, z2, D_A)
    return cone_part(z1, z_cap) + cylinder_part(z_cap, z2, D_A)


def _clamped_part_compliance_cone(
    layers: List[ClampedLayer],
    d_w: float,
    d_h: float,
    tan_phi: float,
    D_A: Optional[float] = None,
) -> float:
    """Clamped-part compliance δ_P [mm/N] via the compression-cone model.

    Two opposed cones grow from the head-side and nut-side bearing faces
    and meet at mid-grip.  The layer stack is walked once from the head
    side; for each infinitesimal slice the governing cone is the one from
    the NEARER bearing face (head cone for z < l_K/2, nut cone mirrored
    for z > l_K/2).  Layers are split at the mid-plane where needed.

    Args:
        layers: Ordered clamped layers (head side first).
        d_w: Bearing (washer face) diameter [mm].
        d_h: Hole diameter [mm].
        tan_phi: tan of the cone half-angle.
        D_A: Limiting available diameter [mm], or None for unlimited.

    Returns:
        Total compliance δ_P [mm/N].
    """
    l_K = sum(max(0.0, l.thickness) for l in layers)
    if l_K <= 0:
        return 0.0
    mid = l_K / 2.0

    # Guard: degenerate bearing geometry → simple cylinder on annulus
    if d_w <= d_h:
        delta = 0.0
        for layer in layers:
            A_eff = math.pi / 4.0 * max(d_w ** 2 - d_h ** 2, 0.0)
            A_eff = max(A_eff, 1.0)
            if layer.youngs_modulus > 0 and layer.thickness > 0:
                delta += layer.thickness / (layer.youngs_modulus * A_eff)
        return delta

    delta_P = 0.0
    z = 0.0  # running depth from head bearing face
    for layer in layers:
        t = max(0.0, layer.thickness)
        E = layer.youngs_modulus
        if t <= 0:
            continue
        z_start, z_end = z, z + t
        z = z_end
        if E <= 0:
            continue

        # Head-side portion of this layer (depth measured from head face)
        a = z_start
        b = min(z_end, mid)
        if b > a:
            delta_P += _frustum_slice_compliance(a, b, E, d_w, d_h, tan_phi, D_A)

        # Nut-side portion (depth measured from nut face)
        a2 = max(z_start, mid)
        if z_end > a2:
            za = l_K - z_end       # depth of layer end from nut face
            zb = l_K - a2          # depth of split point from nut face
            delta_P += _frustum_slice_compliance(za, zb, E, d_w, d_h, tan_phi, D_A)

    return delta_P


def calculate_joint_stiffness(
    bolt_circle: BoltCircle,
    interface: ClampedInterface,
    load_intro_factor_n: float = 0.5,
) -> StiffnessResult:
    """Calculate bolt and clamped-part compliance and force ratio.

    VDI 2230 (2014) §5.1.

    Steps:
      1. Bolt compliance δ_S (head + shank + thread + engaged + nut terms).
      2. Clamped-part compliance δ_P via the compression-cone model.
      3. Basic force ratio φ = δ_P / (δ_S + δ_P).
      4. Load-corrected force ratio φ_n = n · φ.

    Args:
        bolt_circle: Bolt and tightening specification.
        interface: Clamped stack definition with layers.
        load_intro_factor_n: Load introduction factor n ∈ [0, 1].
            0 = load at interface (most conservative for separation).
            1 = load at bolt head/nut (bolt sees full φ share).

    Returns:
        StiffnessResult with δ_S, δ_P, φ, φ_n, n.
    """
    bolt = bolt_circle.bolt
    geom = bolt.geometry

    # --- Step 1: Bolt compliance ---
    delta_S = _bolt_compliance(bolt, interface.total_clamped_length)

    # Bearing face and hole diameters from the bolt geometry tables
    d_w = geom.head_bearing_diameter
    d_h = geom.hole_diameter
    tan_phi = math.tan(math.radians(interface.cone_half_angle_deg))

    # --- Step 2: Clamped-part compliance ---
    delta_P = _clamped_part_compliance_cone(
        interface.layers, d_w, d_h, tan_phi, interface.available_diameter,
    )

    # Protect against degenerate case
    total_compliance = delta_S + delta_P
    if total_compliance <= 0:
        phi_conc = 0.5  # Fallback
    else:
        # --- Step 3: Force ratio φ (concentric) ---
        phi_conc = delta_P / total_compliance

    # --- Step 3b: Eccentric clamping / loading (VDI 2230 §5.3.2) ---
    # δ_P*  = δ_P + s²·l_K/(Ē_P·I_Bers)         (eccentric clamping)
    # δ_P** = δ_P + s·a·l_K/(Ē_P·I_Bers)        (+ eccentric loading)
    # Φ_e   = δ_P** / (δ_S + δ_P*)
    # I_Bers: substitutional bending inertia of the clamp solid,
    # approximated as the annulus of the effective solid diameter
    # D_eff = min(D_A, d_w + l_K·tanφ) — a documented simplification of
    # the VDI substitutional-solid construction.
    s = interface.eccentricity_s
    a = interface.load_eccentricity_a
    phi_basic = phi_conc
    phi_concentric = None
    if (s != 0.0 or a != 0.0) and total_compliance > 0:
        l_K = interface.total_clamped_length
        D_eff = d_w + l_K * tan_phi
        if interface.available_diameter is not None:
            D_eff = min(D_eff, interface.available_diameter)
        I_Bers = math.pi / 64.0 * max(D_eff ** 4 - d_h ** 4, 1.0)
        # Effective clamped-part modulus: series stack Ē = l_K / Σ(t_i/E_i)
        denom_E = sum(
            l.thickness / l.youngs_modulus
            for l in interface.layers
            if l.youngs_modulus > 0 and l.thickness > 0
        )
        E_bar = l_K / denom_E if denom_E > 0 else 0.0
        if E_bar > 0 and I_Bers > 0 and l_K > 0:
            bend_term = l_K / (E_bar * I_Bers)
            delta_P_star = delta_P + s * s * bend_term
            delta_P_star2 = delta_P + s * a * bend_term
            phi_e = delta_P_star2 / (delta_S + delta_P_star)
            phi_basic = min(max(phi_e, 0.0), 1.0)
            phi_concentric = phi_conc

    # --- Step 4: Load-corrected force ratio φ_n ---
    phi_n = load_intro_factor_n * phi_basic

    return StiffnessResult(
        delta_S=delta_S,
        delta_P=delta_P,
        phi_basic=phi_basic,
        phi_n=phi_n,
        load_intro_factor_n=load_intro_factor_n,
        phi_concentric=phi_concentric,
    )

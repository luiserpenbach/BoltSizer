"""Preload calculation module.

Sign convention: forces are positive in tension (bolt stretching direction).
Units: N (force), mm (length), MPa (stress), N·mm (torque).

Method:
  1. Torque → nominal preload via the nut-factor relation
         F_M_nom = M_A / (K · d)
     (NASA-STD-5020B / Bickford convention; VDI 2230 uses the full thread
     torque decomposition — the K shortcut is equivalent for a given K).
  2. Tightening scatter α_A (VDI 2230 Table A8) applied SYMMETRICALLY
     about the nominal:
         ε = (α_A − 1)/(α_A + 1)
         F_M_max = F_M_nom·(1+ε),  F_M_min = F_M_nom·(1−ε)
     so F_M_max/F_M_min = α_A.  If a K range (K_min, K_max) is supplied,
     the envelope of both models is used (conservative in both directions).
  3. Embedding relaxation (VDI 2230 §5.4.2):
         F_Z = f_Z / (δ_S + δ_P)
     with f_Z the sum of the per-region guide values (thread + head/nut
     bearings + inner interfaces) from VDI 2230 Table 5.4.
  4. Net minimum preload: F_V_min = F_M_min − F_Z.
"""
from __future__ import annotations
import math
from typing import Literal, Optional
from boltsizer.models.bolt import Bolt
from boltsizer.models.joint import BoltCircle
from boltsizer.models.results import PreloadResult
from boltsizer.standards.nut_factors import get_scatter_factor

# ---------------------------------------------------------------------------
# LaTeX formula strings (kept adjacent to calculations for traceability)
# ---------------------------------------------------------------------------
FORMULA_TORQUE_TO_PRELOAD = r"F_{M,nom} = \frac{M_A}{K \cdot d}"
FORMULA_SCATTER = (
    r"F_{M,\max/\min} = F_{M,nom}\,(1 \pm \varepsilon),\quad"
    r"\varepsilon = \frac{\alpha_A - 1}{\alpha_A + 1}"
)
FORMULA_EMBEDDING = r"F_Z = \frac{f_Z}{\delta_S + \delta_P}"
FORMULA_NET_PRELOAD_MIN = r"F_{V,\min} = F_{M,\min} - F_Z"

# ---------------------------------------------------------------------------
# VDI 2230 Table 5.4 — embedding amount guide values f_Z [μm] per region.
# Rows: Rz band upper limit [μm]; columns per loading type:
#   (thread, per head/nut bearing surface, per inner interface)
# ---------------------------------------------------------------------------
_EMBEDDING_GUIDE_UM = {
    # Rz <  10 μm
    10.0:  {"axial": (3.0, 2.5, 1.5), "shear": (3.0, 3.0, 2.0)},
    # 10 ≤ Rz < 40 μm
    40.0:  {"axial": (3.0, 3.0, 2.0), "shear": (3.0, 4.5, 2.5)},
    # 40 ≤ Rz < 160 μm
    160.0: {"axial": (3.0, 4.0, 3.0), "shear": (3.0, 6.5, 3.5)},
}


def _get_embedding_displacement(
    num_inner_interfaces: int,
    rz_um: float,
    loading_type: Literal["axial", "shear"] = "axial",
) -> float:
    """Total embedding displacement f_Z [mm] from VDI 2230 Table 5.4 guide values.

    f_Z = f_thread + 2·f_bearing (head + nut) + n_inner·f_interface

    Args:
        num_inner_interfaces: Number of interfaces BETWEEN clamped parts
            (n_parts − 1; washers count as parts).
        rz_um: Governing surface roughness Rz [μm].
        loading_type: "axial" (tension/compression) or "shear"
            (transverse-loaded joints embed more — conservative choice
            whenever the joint carries shear).

    Returns:
        f_Z in mm.
    """
    n_inner = max(0, num_inner_interfaces)
    for rz_limit in sorted(_EMBEDDING_GUIDE_UM):
        if rz_um < rz_limit:
            f_th, f_head, f_inner = _EMBEDDING_GUIDE_UM[rz_limit][loading_type]
            break
    else:
        f_th, f_head, f_inner = _EMBEDDING_GUIDE_UM[160.0][loading_type]

    f_Z_um = f_th + 2.0 * f_head + n_inner * f_inner
    return f_Z_um * 1e-3  # μm → mm


def calculate_preload(
    bolt_circle: BoltCircle,
    grip_length: float,
    total_compliance: Optional[float] = None,
    num_inner_interfaces: Optional[int] = None,
    embedding_loading_type: Literal["axial", "shear"] = "axial",
) -> PreloadResult:
    """Calculate bolt preload including scatter and embedding relaxation.

    Steps:
      1. Convert assembly torque to nominal preload (or use direct target).
      2. Apply symmetric tightening scatter (and K-range envelope if given).
      3. Compute embedding relaxation force F_Z = f_Z/(δ_S + δ_P).
      4. Net minimum preload: F_V_min = F_M_min − F_Z.

    Args:
        bolt_circle: BoltCircle specification including tightening parameters.
        grip_length: Total clamped stack (grip) length l_K [mm].
        total_compliance: δ_S + δ_P of the joint [mm/N].  REQUIRED for a
            correct embedding loss; when None, a bolt-only stiffness
            fallback is used (overestimates F_Z — conservative; only
            intended for previews without joint definition).
        num_inner_interfaces: Interfaces between clamped parts
            (n_layers − 1).  When None, derived from
            bolt_circle.num_mating_surfaces − 1 (treated as a part count).
        embedding_loading_type: "axial" or "shear" — governs the Table 5.4
            guide values (use "shear" when the joint carries shear).

    Returns:
        PreloadResult with all intermediate values.
    """
    bolt = bolt_circle.bolt
    d = bolt.geometry.nominal_diameter       # [mm]
    K = bolt_circle.nut_factor_K
    A_s = bolt.geometry.stress_area          # [mm²]
    E_S = bolt.material.youngs_modulus       # [MPa]

    # --- Step 1: Nominal preload ---
    torque_mode = bolt_circle.assembly_torque > 0
    if torque_mode:
        F_M_nominal = bolt_circle.assembly_torque / (K * d)
    else:
        # Direct target preload mode
        F_M_nominal = bolt_circle.target_preload

    # --- Step 2: Tightening scatter (symmetric about nominal) ---
    alpha_A = get_scatter_factor(bolt_circle.tightening_method)
    eps = (alpha_A - 1.0) / (alpha_A + 1.0)
    F_M_max = F_M_nominal * (1.0 + eps)
    F_M_min = F_M_nominal * (1.0 - eps)

    # K-range envelope: low friction → higher preload at same torque,
    # high friction → lower preload.  Take the wider (conservative) bounds.
    if torque_mode:
        K_min = bolt_circle.nut_factor_K_min
        K_max = bolt_circle.nut_factor_K_max
        if K_min is not None and K_min > 0:
            F_M_max = max(F_M_max, bolt_circle.assembly_torque / (K_min * d))
        if K_max is not None and K_max > 0:
            F_M_min = min(F_M_min, bolt_circle.assembly_torque / (K_max * d))

    # --- Step 3: Embedding relaxation ---
    if num_inner_interfaces is None:
        num_inner_interfaces = max(0, bolt_circle.num_mating_surfaces - 1)
    f_Z = _get_embedding_displacement(
        num_inner_interfaces,
        bolt_circle.surface_roughness_Rz,
        embedding_loading_type,
    )
    # F_Z = f_Z / (δ_S + δ_P)   (VDI 2230 §5.4.2)
    if total_compliance is not None and total_compliance > 0:
        F_Z = f_Z / total_compliance
    elif grip_length > 0:
        # Bolt-only stiffness fallback (preview use only): overestimates
        # the loss because the clamped-part compliance is neglected.
        F_Z = f_Z * E_S * A_s / grip_length
    else:
        F_Z = 0.0

    # --- Step 4: Net minimum preload ---
    F_preload_min = max(0.0, F_M_min - F_Z)
    F_preload_max = F_M_max  # Embedding doesn't increase preload

    return PreloadResult(
        F_M_nominal=F_M_nominal,
        F_M_max=F_M_max,
        F_M_min=F_M_min,
        F_Z=F_Z,
        F_preload_max=F_preload_max,
        F_preload_min=F_preload_min,
        alpha_A=alpha_A,
        f_Z_displacement=f_Z,
    )

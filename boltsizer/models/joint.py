"""Joint geometry and loading data models.

Sign convention: axial tension is positive throughout.
All dimensions in mm, forces in N, stresses in MPa, moments in N·mm.
"""
from dataclasses import dataclass, field
from typing import Literal, List
from .bolt import Bolt


@dataclass
class ClampedLayer:
    """Single layer in the clamped stack.

    Attributes:
        material: Material name (used to look up E from material library).
        thickness: Layer thickness [mm].
        youngs_modulus: E [MPa]; if None, looked up from material library.
    """
    material: str
    thickness: float            # [mm]
    youngs_modulus: float       # [MPa]


@dataclass
class ClampedInterface:
    """Description of the clamped joint interface.

    Attributes:
        total_clamped_length: Total grip length l_K [mm] — sum of all layer thicknesses.
        layers: Ordered list of layers from bolt head to nut.
        interface_treatment: Surface finish at the shear interface.
        friction_coefficient: Coefficient of friction μ at interface for slip check.
        num_friction_interfaces: Number of friction interfaces n_i for slip check.
    """
    total_clamped_length: float          # [mm] grip length l_K
    layers: List[ClampedLayer]
    interface_treatment: str
    friction_coefficient: float          # μ
    num_friction_interfaces: int = 1

    def __post_init__(self):
        # Recompute total from layers if layers provided
        if self.layers:
            computed = sum(layer.thickness for layer in self.layers)
            # Allow small floating-point deviation; trust layers sum
            self.total_clamped_length = computed


@dataclass
class BoltCircle:
    """Bolt pattern / bolt circle definition.

    Attributes:
        num_bolts: Number of bolts n_B.
        bolt_circle_diameter: Pitch circle diameter (PCD) [mm].
        bolt: Bolt specification (same for all bolts in pattern).
        nut_factor_K: Nut/K-factor for torque-to-preload conversion.
        assembly_torque: Tightening torque M_A [N·mm].
        target_preload: Alternative to torque — direct preload input [N].
        tightening_method: Method used; governs scatter factor α_A.
        num_mating_surfaces: Number of mating/embedding surfaces for f_Z.
        surface_roughness_Rz: Mean surface roughness Rz [μm] for embedding.
    """
    num_bolts: int
    bolt_circle_diameter: float          # [mm] PCD
    bolt: Bolt
    nut_factor_K: float
    assembly_torque: float = 0.0         # [N·mm] M_A; set 0 if using target_preload
    target_preload: float = 0.0          # [N]; used when assembly_torque == 0
    tightening_method: str = "torque_wrench"
    num_mating_surfaces: int = 2
    surface_roughness_Rz: float = 6.3    # [μm]


@dataclass
class ExternalLoading:
    """External loads applied to the bolt circle.

    Sign convention:
        axial_force:     tension positive [N]
        bending_moment:  [N·mm], axis perpendicular to bolt circle axis
        shear_force:     [N], in the bolt circle plane
        torsion:         [N·mm], about the bolt circle axis

    Attributes:
        axial_force: Net axial (opening) force F_A [N].
        bending_moment: Bending moment M_B [N·mm].
        shear_force: Shear force Q [N].
        torsion: Torsional moment M_T [N·mm] (usually friction-reacted, not in bolts).
        load_plane: Where load is introduced: "interface" or "bolt_head".
        load_factor: Design load factor (e.g. ECSS safety factor).
        case_name: Identifier for this load case.
    """
    axial_force: float           # [N] tension +
    bending_moment: float        # [N·mm]
    shear_force: float           # [N]
    torsion: float = 0.0         # [N·mm]
    load_plane: Literal["interface", "bolt_head"] = "interface"
    load_factor: float = 1.0
    case_name: str = "LC1"

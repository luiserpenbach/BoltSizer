"""Joint geometry and loading data models.

Sign convention: axial tension is positive throughout.
All dimensions in mm, forces in N, stresses in MPa, moments in N·mm.
"""
from dataclasses import dataclass, field
from typing import Literal, List, Optional
from .bolt import Bolt


@dataclass
class ClampedLayer:
    """Single layer in the clamped stack.

    Attributes:
        material: Material name (used to look up E from material library).
        thickness: Layer thickness [mm].
        youngs_modulus: E [MPa]; if None, looked up from material library.
        cte: Coefficient of thermal expansion [1/K]; if None, looked up
            from the flange material CTE table (fallback 11.5e-6, steel).
    """
    material: str
    thickness: float            # [mm]
    youngs_modulus: float       # [MPa]
    cte: Optional[float] = None  # [1/K]


@dataclass
class ClampedInterface:
    """Description of the clamped joint interface.

    Attributes:
        total_clamped_length: Total grip length l_K [mm] — sum of all layer thicknesses.
        layers: Ordered list of layers from bolt head to nut.
        interface_treatment: Surface finish at the shear interface.
        friction_coefficient: Coefficient of friction μ at interface for slip check.
        num_friction_interfaces: Number of friction interfaces n_i for slip check.
        available_diameter: Limiting outer diameter D_A [mm] available for the
            compression cone (min of bolt pitch spacing and 2× edge distance).
            None → cone spreads without limit (only valid for wide flanges).
        cone_half_angle_deg: Compression cone half-angle φ_K [deg].
            Default 30° (classic Rotscher/Shigley assumption; VDI 2230
            computes joint-specific angles — 30° is a reasonable mid value).
        eccentricity_s: Distance s_sym between the bolt axis and the axis
            of the clamp solid [mm] (VDI 2230 §5.3.2). 0 = concentric.
        load_eccentricity_a: Distance a between the axial-load line of
            action and the clamp-solid axis [mm], same side as s positive.
            0 = concentric loading.
    """
    total_clamped_length: float          # [mm] grip length l_K
    layers: List[ClampedLayer]
    interface_treatment: str
    friction_coefficient: float          # μ
    num_friction_interfaces: int = 1
    available_diameter: Optional[float] = None   # [mm] D_A cone limit
    cone_half_angle_deg: float = 30.0
    eccentricity_s: float = 0.0          # [mm] s_sym
    load_eccentricity_a: float = 0.0     # [mm] a

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
        nut_factor_K: Nominal nut/K-factor for torque-to-preload conversion.
        assembly_torque: Tightening torque M_A [N·mm].
        target_preload: Alternative to torque — direct preload input [N].
        tightening_method: Method used; governs scatter factor α_A.
        num_mating_surfaces: Number of clamped parts in the stack (used for
            the embedding estimate when the layer list is not available;
            the analysis orchestrator overrides this with len(layers)).
        surface_roughness_Rz: Mean surface roughness Rz [μm] for embedding.
        nut_factor_K_min: Optional lower K bound (e.g. coating table K_min).
            When given, the preload envelope includes M_A/(K_min·d) as a
            possible maximum preload (low friction → high preload).
        nut_factor_K_max: Optional upper K bound; envelope includes
            M_A/(K_max·d) as a possible minimum preload.
        tool_scatter_pct: Torque-tool accuracy as a fraction (e.g. 0.05 for
            ±5%).  Composed MULTIPLICATIVELY with the K-range bounds
            (ECSS / SpaceBolt convention: friction extremes × tool
            scatter).  Only used when a K range is given.
        embedding_percent_of_max: Alternative embedding model — preload
            loss as a fraction of the maximum preload (e.g. 0.05 for the
            common 5% assumption).  None → VDI 2230 Table 5.4 guide values.
        pattern: Bolt pattern type — "circle" (num_bolts on the PCD),
            "rectangle" (rect_nx × rect_ny grid), or "custom"
            (explicit XY positions).  Bending is resolved about the
            pattern centroid with the moment axis along Y (bolt axial
            force ∝ x-coordinate), matching the circle convention.
        rect_nx / rect_ny: Grid counts for the rectangle pattern.
        rect_pitch_x / rect_pitch_y: Grid pitches [mm].
        custom_positions: [(x, y), ...] bolt positions [mm] for "custom".
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
    nut_factor_K_min: Optional[float] = None
    nut_factor_K_max: Optional[float] = None
    tool_scatter_pct: Optional[float] = None
    embedding_percent_of_max: Optional[float] = None
    pattern: Literal["circle", "rectangle", "custom"] = "circle"
    rect_nx: int = 2
    rect_ny: int = 2
    rect_pitch_x: float = 60.0
    rect_pitch_y: float = 60.0
    custom_positions: Optional[List[tuple]] = None

    def bolt_positions(self) -> List[tuple]:
        """Bolt XY positions [mm] about the pattern centroid."""
        import math as _math
        if self.pattern == "rectangle":
            nx, ny = max(1, self.rect_nx), max(1, self.rect_ny)
            x0 = -(nx - 1) * self.rect_pitch_x / 2.0
            y0 = -(ny - 1) * self.rect_pitch_y / 2.0
            return [
                (x0 + i * self.rect_pitch_x, y0 + j * self.rect_pitch_y)
                for j in range(ny) for i in range(nx)
            ]
        if self.pattern == "custom" and self.custom_positions:
            xs = [p[0] for p in self.custom_positions]
            ys = [p[1] for p in self.custom_positions]
            cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
            return [(x - cx, y - cy) for x, y in self.custom_positions]
        # circle (default)
        r = self.bolt_circle_diameter / 2.0
        n = max(1, self.num_bolts)
        return [
            (r * _math.cos(2 * _math.pi * i / n), r * _math.sin(2 * _math.pi * i / n))
            for i in range(n)
        ]

    @property
    def effective_num_bolts(self) -> int:
        """Bolt count for the active pattern."""
        if self.pattern == "rectangle":
            return max(1, self.rect_nx) * max(1, self.rect_ny)
        if self.pattern == "custom" and self.custom_positions:
            return len(self.custom_positions)
        return max(1, self.num_bolts)


@dataclass
class ExternalLoading:
    """External loads applied to the bolt circle.

    Sign convention:
        axial_force:     tension positive [N]
        bending_moment:  [N·mm], axis perpendicular to bolt circle axis
        shear_force:     [N], in the bolt circle plane
        torsion:         [N·mm], about the bolt circle axis — reacted as
                         tangential shear on the bolts (conservative; if a
                         shear pin or spigot reacts it, enter 0).

    Attributes:
        axial_force: Net axial (opening) force F_A [N] — maximum of the cycle.
        bending_moment: Bending moment M_B [N·mm] — maximum of the cycle.
        shear_force: Shear force Q [N].
        torsion: Torsional moment M_T [N·mm] about the circle axis.
        axial_force_min: Minimum axial force of the load cycle [N]
            (0 = pulsating, −axial_force = fully reversed). Used for the
            fatigue amplitude.
        bending_moment_min: Minimum bending moment of the cycle [N·mm].
        delta_T: Temperature change from assembly [K]. Positive = hotter.
            Used for the thermal preload change with the joint CTEs.
        load_plane: Where load is introduced: "interface" or "bolt_head".
            "bolt_head" forces the load-introduction factor n = 1 for this
            case (bolt sees the full φ share — conservative for the bolt).
        load_factor: Design load factor (e.g. ECSS safety factor).
        case_name: Identifier for this load case.
    """
    axial_force: float           # [N] tension +
    bending_moment: float        # [N·mm]
    shear_force: float           # [N]
    torsion: float = 0.0         # [N·mm]
    axial_force_min: float = 0.0     # [N]
    bending_moment_min: float = 0.0  # [N·mm]
    delta_T: float = 0.0             # [K]
    load_plane: Literal["interface", "bolt_head"] = "interface"
    load_factor: float = 1.0
    case_name: str = "LC1"

"""Bolt geometry and material data models.

Sign convention: axial tension is positive throughout.
All dimensions in mm, forces in N, stresses in MPa.
"""
from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class BoltGeometry:
    """Geometric properties of a bolt.

    Attributes:
        standard: Thread standard, e.g. "ISO metric" or "Unified".
        designation: Bolt size string, e.g. "M8" or "1/4-20 UNC".
        nominal_diameter: Nominal (major) diameter [mm].
        pitch: Thread pitch [mm] (or converted pitch for unified).
        stress_area: Tensile stress area A_s [mm²] per ISO 898-1 / ASME B1.1.
        head_bearing_area: Bearing area under bolt head / nut [mm²]
            = π/4·(d_w² − d_h²).
        shank_length: Unthreaded shank length [mm].
        threaded_length: Length of threaded engagement [mm].
        minor_diameter: Minor (root) diameter d3 [mm], used for torsion.
        pitch_diameter: Pitch diameter d2 [mm], used for K-factor derivation.
        head_bearing_diameter: Bearing (washer face) outer diameter d_w [mm]
            (ISO 4014/4017 minimum for metric hex; ≈1.4·d fallback otherwise).
        hole_diameter: Clearance hole diameter d_h [mm]
            (ISO 273 medium series for metric; ≈1.06·d fallback otherwise).
    """
    standard: str               # "ISO metric" | "Unified"
    designation: str            # e.g. "M8", "1/4-20 UNC"
    nominal_diameter: float     # [mm]
    pitch: float                # [mm]
    stress_area: float          # [mm²] — tensile stress area
    head_bearing_area: float    # [mm²]
    shank_length: float         # [mm]
    threaded_length: float      # [mm]
    minor_diameter: float       # [mm] d3
    pitch_diameter: float       # [mm] d2
    head_bearing_diameter: float = 0.0   # [mm] d_w; 0 → 1.4·d fallback
    hole_diameter: float = 0.0           # [mm] d_h; 0 → 1.06·d fallback

    def __post_init__(self):
        if self.head_bearing_diameter <= 0:
            self.head_bearing_diameter = 1.4 * self.nominal_diameter
        if self.hole_diameter <= 0:
            self.hole_diameter = 1.06 * self.nominal_diameter

    @property
    def stress_diameter(self) -> float:
        """Stress diameter d_s = (d2 + d3)/2 per VDI 2230 §5.5.1 [mm]."""
        return 0.5 * (self.pitch_diameter + self.minor_diameter)

    @property
    def nominal_area(self) -> float:
        """Nominal cross-section area A_N = π/4·d² [mm²]."""
        import math
        return math.pi / 4.0 * self.nominal_diameter ** 2

    @property
    def minor_area(self) -> float:
        """Minor-diameter cross-section area A_d3 = π/4·d3² [mm²]."""
        import math
        return math.pi / 4.0 * self.minor_diameter ** 2


@dataclass
class BoltMaterial:
    """Material properties for a bolt.

    Attributes:
        name: Material/grade name, e.g. "A286", "ISO 8.8", "Inconel 718".
        yield_strength: 0.2% proof / yield strength R_p0.2 [MPa].
        uts: Ultimate tensile strength R_m [MPa].
        youngs_modulus: Young's modulus E [MPa].
        fatigue_limit: OPTIONAL user override for the bolt-thread endurance
            stress amplitude σ_AS [MPa].  When None (default), the fatigue
            check computes the VDI 2230 §5.5.3 thread endurance limit
            σ_ASV = 0.85·(150/d + 45) (rolled before heat treatment), or
            σ_ASG for threads rolled after heat treatment.  Only set this
            when fastener-specific test data is available — smooth-bar
            fatigue limits must NOT be used here.
        proof_load_stress: Proof load stress R_p [MPa] (= yield_strength if not
            separately defined).
        cte: Coefficient of thermal expansion α_S [1/K] for thermal preload
            loss.  None → thermal effects for the bolt use 11.5e-6 (steel).
    """
    name: str
    yield_strength: float       # [MPa]
    uts: float                  # [MPa]
    youngs_modulus: float       # [MPa]
    fatigue_limit: Optional[float] = None   # [MPa] override only
    proof_load_stress: Optional[float] = None  # [MPa]
    cte: Optional[float] = None  # [1/K]

    def __post_init__(self):
        if self.proof_load_stress is None:
            self.proof_load_stress = self.yield_strength


@dataclass
class Bolt:
    """Complete bolt specification.

    Attributes:
        geometry: Geometric properties of the bolt.
        material: Material / grade properties.
        grade: Grade designation string, e.g. "ISO 898 Grade 8.8".
        coating: Surface finish / coating, e.g. "Cadmium", "MoS2", "None".
        thread_rolled: "before_ht" (rolled before heat treatment — standard
            production bolts, conservative default) or "after_ht" (rolled
            after heat treatment — aerospace practice, higher fatigue
            allowable per VDI 2230 §5.5.3).
    """
    geometry: BoltGeometry
    material: BoltMaterial
    grade: str
    coating: str = "None"
    thread_rolled: Literal["before_ht", "after_ht"] = "before_ht"

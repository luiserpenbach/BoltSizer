"""Bolt geometry and material data models.

Sign convention: axial tension is positive throughout.
All dimensions in mm, forces in N, stresses in MPa.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BoltGeometry:
    """Geometric properties of a bolt.

    Attributes:
        standard: Thread standard, e.g. "ISO metric" or "Unified".
        designation: Bolt size string, e.g. "M8" or "1/4-20 UNC".
        nominal_diameter: Nominal (major) diameter [mm].
        pitch: Thread pitch [mm] (or converted pitch for unified).
        stress_area: Tensile stress area A_s [mm²] per ISO 898-1 / ASME B1.1.
        head_bearing_area: Bearing area under bolt head / nut [mm²].
        shank_length: Unthreaded shank length [mm].
        threaded_length: Length of threaded engagement [mm].
        minor_diameter: Minor (root) diameter d3 [mm], used for torsion.
        pitch_diameter: Pitch diameter d2 [mm], used for K-factor derivation.
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


@dataclass
class BoltMaterial:
    """Material properties for a bolt.

    Attributes:
        name: Material/grade name, e.g. "A286", "ISO 8.8", "Inconel 718".
        yield_strength: 0.2% proof / yield strength R_p0.2 [MPa].
        uts: Ultimate tensile strength R_m [MPa].
        youngs_modulus: Young's modulus E [MPa].
        fatigue_limit: Fully-reversed fatigue limit σ_A [MPa].
                       None if not applicable (use allowable = 0 in check).
        proof_load_stress: Proof load stress R_p [MPa] (= yield_strength if not
                           separately defined).
    """
    name: str
    yield_strength: float       # [MPa]
    uts: float                  # [MPa]
    youngs_modulus: float       # [MPa]
    fatigue_limit: Optional[float] = None   # [MPa]
    proof_load_stress: Optional[float] = None  # [MPa]

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
    """
    geometry: BoltGeometry
    material: BoltMaterial
    grade: str
    coating: str = "None"

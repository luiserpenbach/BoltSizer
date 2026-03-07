"""Bolt and flange material property tables.

Sources:
  ISO 898-1:2013  — ISO metric bolt grades 4.6, 8.8, 10.9, 12.9
  AMS 5737        — A286 age-hardened (Alloy 286)
  AMS 5662        — Inconel 718 SHT + aged
  AMS 4928        — Ti-6Al-4V ELI
  ISO 3506-1      — Stainless steel A2-70, A4-80

Fatigue limits are stress amplitude at R = -1 (fully reversed), estimated at 10^7 cycles.
For bolted joints, use A_s · σ_a as the fatigue force allowable.

All properties in MPa and GPa (converted to MPa in entries).
"""
from __future__ import annotations
from typing import Dict, Optional
from boltsizer.models.bolt import BoltMaterial

# ---------------------------------------------------------------------------
# Grade tables — keys are grade/designation strings
# ---------------------------------------------------------------------------
MATERIAL_LIBRARY: Dict[str, Dict] = {
    # ISO 898-1 Carbon steel grades
    "ISO 4.6": dict(
        name="ISO 4.6",
        yield_strength=240,
        uts=400,
        youngs_modulus=210000,
        fatigue_limit=90,
        proof_load_stress=225,
        source="ISO 898-1:2013",
    ),
    "ISO 8.8": dict(
        name="ISO 8.8",
        yield_strength=640,
        uts=800,
        youngs_modulus=210000,
        fatigue_limit=129,  # ≈ 0.16 · UTS (VDI 2230 Table A8 estimate)
        proof_load_stress=600,
        source="ISO 898-1:2013",
    ),
    "ISO 10.9": dict(
        name="ISO 10.9",
        yield_strength=900,
        uts=1040,
        youngs_modulus=210000,
        fatigue_limit=150,
        proof_load_stress=830,
        source="ISO 898-1:2013",
    ),
    "ISO 12.9": dict(
        name="ISO 12.9",
        yield_strength=1080,
        uts=1220,
        youngs_modulus=210000,
        fatigue_limit=170,
        proof_load_stress=970,
        source="ISO 898-1:2013",
    ),
    # Stainless steel (ISO 3506-1)
    "A2-70": dict(
        name="A2-70 Stainless",
        yield_strength=450,
        uts=700,
        youngs_modulus=193000,
        fatigue_limit=100,
        proof_load_stress=420,
        source="ISO 3506-1",
    ),
    "A4-80": dict(
        name="A4-80 Stainless",
        yield_strength=600,
        uts=800,
        youngs_modulus=193000,
        fatigue_limit=120,
        proof_load_stress=560,
        source="ISO 3506-1",
    ),
    # Aerospace alloys
    "A286": dict(
        name="A286 (age-hardened)",
        yield_strength=793,
        uts=1000,
        youngs_modulus=200000,
        fatigue_limit=380,  # Per Shigley / AMS 5737 fatigue data
        proof_load_stress=793,
        source="AMS 5737",
    ),
    "Inconel 718": dict(
        name="Inconel 718 (SHT+aged)",
        yield_strength=1034,
        uts=1241,
        youngs_modulus=200000,
        fatigue_limit=450,
        proof_load_stress=1034,
        source="AMS 5662",
    ),
    "Ti-6Al-4V ELI": dict(
        name="Ti-6Al-4V ELI",
        yield_strength=828,
        uts=896,
        youngs_modulus=113000,
        fatigue_limit=340,
        proof_load_stress=828,
        source="AMS 4928",
    ),
    "Ti-6Al-4V": dict(
        name="Ti-6Al-4V",
        yield_strength=880,
        uts=950,
        youngs_modulus=114000,
        fatigue_limit=350,
        proof_load_stress=880,
        source="AMS 4928 / AMS 4967",
    ),
    "Custom": dict(
        name="Custom",
        yield_strength=0,
        uts=0,
        youngs_modulus=210000,
        fatigue_limit=None,
        proof_load_stress=0,
        source="User defined",
    ),
}

# Flange/clamped-part material Young's moduli for compliance calculation
FLANGE_MATERIAL_E: Dict[str, float] = {
    "Steel (carbon)": 210000,       # [MPa]
    "Steel (stainless)": 193000,
    "Aluminium alloy": 70000,
    "Titanium alloy": 114000,
    "Inconel 718": 200000,
    "CFRP (quasi-isotropic)": 60000,
    "GFRP": 25000,
    "Copper alloy": 120000,
    "Cast iron": 170000,
}


def get_material(grade: str) -> BoltMaterial:
    """Return a BoltMaterial from the library.

    Args:
        grade: Grade key string, e.g. "ISO 8.8", "A286", "Inconel 718".

    Returns:
        BoltMaterial instance.

    Raises:
        KeyError: If grade not in library.
    """
    if grade not in MATERIAL_LIBRARY:
        available = ", ".join(sorted(MATERIAL_LIBRARY.keys()))
        raise KeyError(f"Grade '{grade}' not in library. Available: {available}")
    d = MATERIAL_LIBRARY[grade]
    return BoltMaterial(
        name=d["name"],
        yield_strength=d["yield_strength"],
        uts=d["uts"],
        youngs_modulus=d["youngs_modulus"],
        fatigue_limit=d.get("fatigue_limit"),
        proof_load_stress=d.get("proof_load_stress", d["yield_strength"]),
    )

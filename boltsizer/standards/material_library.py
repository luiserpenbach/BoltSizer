"""Bolt and flange material property tables.

Sources:
  ISO 898-1:2013  — ISO metric bolt grades 4.6, 8.8, 10.9, 12.9
  AMS 5737        — A286 age-hardened (Alloy 286)
  AMS 5662        — Inconel 718 SHT + aged
  AMS 4928        — Ti-6Al-4V ELI
  ISO 3506-1      — Stainless steel A2-70, A4-80

Strength values are the ISO 898-1 Table 3 MINIMUM values (not nominal).
Size-dependent grades (8.8) are resolved in get_material() via the
nominal diameter.

Fatigue: bolt-thread endurance limits are NOT stored per material.
Smooth-bar fatigue limits must never be compared against bolt thread
stresses — the thread notch dominates.  The fatigue check computes the
VDI 2230 §5.5.3 thread endurance limit (σ_ASV / σ_ASG) from the bolt
diameter and thread-rolling condition.  `fatigue_limit` may be set by
the user as an explicit override when fastener-specific test data exists.

All properties in MPa; CTE in 1/K.
"""
from __future__ import annotations
from typing import Dict, Optional
from boltsizer.models.bolt import BoltMaterial

# ---------------------------------------------------------------------------
# Grade tables — keys are grade/designation strings
# ---------------------------------------------------------------------------
MATERIAL_LIBRARY: Dict[str, Dict] = {
    # ISO 898-1 Carbon steel grades (Table 3 minimum values)
    "ISO 4.6": dict(
        name="ISO 4.6",
        yield_strength=240,
        uts=400,
        youngs_modulus=210000,
        proof_load_stress=225,
        cte=11.5e-6,
        source="ISO 898-1:2013",
    ),
    "ISO 8.8": dict(
        name="ISO 8.8",
        # d <= M16 values; get_material() switches to 660/830/600 above M16.
        yield_strength=640,
        uts=800,
        youngs_modulus=210000,
        proof_load_stress=580,
        cte=11.5e-6,
        source="ISO 898-1:2013",
        # Size-dependent overrides applied for d > 16 mm:
        over_16mm=dict(yield_strength=660, uts=830, proof_load_stress=600),
    ),
    "ISO 10.9": dict(
        name="ISO 10.9",
        yield_strength=940,
        uts=1040,
        youngs_modulus=210000,
        proof_load_stress=830,
        cte=11.5e-6,
        source="ISO 898-1:2013",
    ),
    "ISO 12.9": dict(
        name="ISO 12.9",
        yield_strength=1100,
        uts=1220,
        youngs_modulus=210000,
        proof_load_stress=970,
        cte=11.5e-6,
        source="ISO 898-1:2013",
    ),
    # Stainless steel (ISO 3506-1)
    "A2-70": dict(
        name="A2-70 Stainless",
        yield_strength=450,
        uts=700,
        youngs_modulus=193000,
        proof_load_stress=420,
        cte=16.0e-6,
        source="ISO 3506-1",
    ),
    "A4-80": dict(
        name="A4-80 Stainless",
        yield_strength=600,
        uts=800,
        youngs_modulus=193000,
        proof_load_stress=560,
        cte=16.0e-6,
        source="ISO 3506-1",
    ),
    # Aerospace alloys
    "A286": dict(
        name="A286 (age-hardened)",
        yield_strength=793,
        uts=1000,
        youngs_modulus=200000,
        proof_load_stress=793,
        cte=16.5e-6,
        source="AMS 5737",
    ),
    "Inconel 718": dict(
        name="Inconel 718 (SHT+aged)",
        yield_strength=1034,
        uts=1241,
        youngs_modulus=200000,
        proof_load_stress=1034,
        cte=13.0e-6,
        source="AMS 5662",
    ),
    "Ti-6Al-4V ELI": dict(
        name="Ti-6Al-4V ELI",
        yield_strength=828,
        uts=896,
        youngs_modulus=113000,
        proof_load_stress=828,
        cte=8.6e-6,
        source="AMS 4928",
    ),
    "Ti-6Al-4V": dict(
        name="Ti-6Al-4V",
        yield_strength=880,
        uts=950,
        youngs_modulus=114000,
        proof_load_stress=880,
        cte=8.6e-6,
        source="AMS 4928 / AMS 4967",
    ),
    # "Custom" requires explicit user-supplied properties — the API rejects
    # analyses that select Custom without providing them.
    "Custom": dict(
        name="Custom",
        yield_strength=0,
        uts=0,
        youngs_modulus=210000,
        proof_load_stress=0,
        cte=11.5e-6,
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

# Flange/clamped-part coefficients of thermal expansion [1/K]
# (representative room-temperature values; CFRP is the in-plane quasi-
# isotropic value)
FLANGE_MATERIAL_CTE: Dict[str, float] = {
    "Steel (carbon)": 11.5e-6,
    "Steel (stainless)": 16.0e-6,
    "Aluminium alloy": 23.0e-6,
    "Titanium alloy": 8.6e-6,
    "Inconel 718": 13.0e-6,
    "CFRP (quasi-isotropic)": 3.0e-6,
    "GFRP": 20.0e-6,
    "Copper alloy": 17.0e-6,
    "Cast iron": 10.5e-6,
}

_DEFAULT_CTE = 11.5e-6  # steel fallback [1/K]


def get_flange_cte(material_name: str) -> float:
    """Return the CTE for a flange material name (steel fallback)."""
    return FLANGE_MATERIAL_CTE.get(material_name, _DEFAULT_CTE)


def get_material(grade: str, nominal_diameter: Optional[float] = None) -> BoltMaterial:
    """Return a BoltMaterial from the library.

    Args:
        grade: Grade key string, e.g. "ISO 8.8", "A286", "Inconel 718".
        nominal_diameter: Bolt nominal diameter [mm].  Required to resolve
            size-dependent grades correctly (ISO 8.8 property step at M16);
            when omitted, the ≤M16 values are returned.

    Returns:
        BoltMaterial instance.

    Raises:
        KeyError: If grade not in library.
    """
    if grade not in MATERIAL_LIBRARY:
        available = ", ".join(sorted(MATERIAL_LIBRARY.keys()))
        raise KeyError(f"Grade '{grade}' not in library. Available: {available}")
    d = MATERIAL_LIBRARY[grade]

    yield_strength = d["yield_strength"]
    uts = d["uts"]
    proof = d.get("proof_load_stress", d["yield_strength"])
    if nominal_diameter is not None and nominal_diameter > 16.0 and "over_16mm" in d:
        ov = d["over_16mm"]
        yield_strength = ov.get("yield_strength", yield_strength)
        uts = ov.get("uts", uts)
        proof = ov.get("proof_load_stress", proof)

    return BoltMaterial(
        name=d["name"],
        yield_strength=yield_strength,
        uts=uts,
        youngs_modulus=d["youngs_modulus"],
        fatigue_limit=d.get("fatigue_limit"),  # None unless explicitly set
        proof_load_stress=proof,
        cte=d.get("cte"),
    )

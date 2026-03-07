"""ISO Metric and Unified bolt property tables.

Sources:
  ISO 898-1:2013 — Mechanical properties of fasteners — bolts, screws and studs
  ISO 724:1993   — ISO general-purpose metric screw threads
  ASME B1.1-2003 — Unified inch screw threads

All dimensions in mm. Stress areas per ISO 898-1 Annex B / ASME B1.1.

Tensile stress area formula (ISO):
  A_s = π/4 · ((d2 + d3) / 2)² where d2 = pitch diameter, d3 = minor diameter
  d2 = d - 0.6495 · p,  d3 = d - 1.2269 · p
"""
from __future__ import annotations
from typing import Dict, Optional
from boltsizer.models.bolt import BoltGeometry

# ---------------------------------------------------------------------------
# ISO Metric bolt table — coarse pitch (ISO 261 preferred series)
# Fields: (nominal_d_mm, pitch_mm, stress_area_mm2, pitch_diam_mm, minor_diam_mm, head_bearing_area_mm2)
# head_bearing_area estimated as π/4*(d_w² - d_hole²) where d_w ≈ 1.5*d and d_hole ≈ d
# ---------------------------------------------------------------------------
_ISO_METRIC_COARSE: Dict[str, tuple] = {
    #  desig  :  d     p      A_s    d2      d3     A_bear
    "M3":    (3.0,   0.50,  5.03,  2.675,  2.387,  5.0),
    "M4":    (4.0,   0.70,  8.78,  3.545,  3.141,  9.0),
    "M5":    (5.0,   0.80, 14.20,  4.480,  4.019, 14.0),
    "M6":    (6.0,   1.00, 20.10,  5.350,  4.773, 20.0),
    "M8":    (8.0,   1.25, 36.60,  7.188,  6.466, 37.0),
    "M10":   (10.0,  1.50, 58.00,  9.026,  8.160, 58.0),
    "M12":   (12.0,  1.75, 84.30, 10.863,  9.853, 84.0),
    "M14":   (14.0,  2.00,115.0,  12.701, 11.546,115.0),
    "M16":   (16.0,  2.00,157.0,  14.701, 13.546,160.0),
    "M18":   (18.0,  2.50,192.0,  16.376, 14.933,195.0),
    "M20":   (20.0,  2.50,245.0,  18.376, 16.933,250.0),
    "M22":   (22.0,  2.50,303.0,  20.376, 18.933,305.0),
    "M24":   (24.0,  3.00,353.0,  22.051, 20.320,360.0),
    "M27":   (27.0,  3.00,459.0,  25.051, 23.320,465.0),
    "M30":   (30.0,  3.50,561.0,  27.727, 25.706,570.0),
    "M36":   (36.0,  4.00,817.0,  33.402, 31.093,830.0),
}

# ISO Metric — fine pitch selected sizes (designation = "MXxY" e.g. "M10x1.25")
_ISO_METRIC_FINE: Dict[str, tuple] = {
    "M8x1":      (8.0,  1.00, 39.17, 7.350, 6.773, 37.0),
    "M10x1.25":  (10.0, 1.25, 61.20, 9.188, 8.466, 58.0),
    "M10x1":     (10.0, 1.00, 64.50, 9.350, 8.773, 58.0),
    "M12x1.5":   (12.0, 1.50, 88.10, 11.026, 10.160, 84.0),
    "M12x1.25":  (12.0, 1.25, 92.10, 11.188, 10.466, 84.0),
    "M16x1.5":   (16.0, 1.50,167.0, 15.026, 14.160,160.0),
    "M20x1.5":   (20.0, 1.50,259.0, 19.026, 18.160,250.0),
    "M24x2":     (24.0, 2.00,384.0, 22.701, 21.546,360.0),
}

# Unified (UNC/UNF) bolt table — dimensions converted to mm
# pitch = 25.4 / TPI
_UNIFIED: Dict[str, tuple] = {
    #  desig             d_mm    p_mm    A_s_mm2  d2_mm   d3_mm  A_bear_mm2
    "1/4-20 UNC":   (6.350,  1.270,  20.52,  5.537,  4.916,  20.0),
    "1/4-28 UNF":   (6.350,  0.907,  22.00,  5.741,  5.271,  22.0),
    "5/16-18 UNC":  (7.938,  1.411,  34.63,  6.928,  6.143,  33.0),
    "5/16-24 UNF":  (7.938,  1.058,  37.42,  7.121,  6.552,  36.0),
    "3/8-16 UNC":   (9.525,  1.588,  52.00,  8.306,  7.362,  50.0),
    "3/8-24 UNF":   (9.525,  1.058,  56.60,  8.668,  7.999,  55.0),
    "7/16-14 UNC":  (11.113, 1.814,  71.60,  9.677,  8.583,  70.0),
    "1/2-13 UNC":   (12.700, 1.954,  93.50, 11.062,  9.792,  90.0),
    "1/2-20 UNF":   (12.700, 1.270, 103.0,  11.468, 10.641, 100.0),
    "9/16-12 UNC":  (14.288, 2.117, 119.0,  12.447, 11.022,115.0),
    "5/8-11 UNC":   (15.875, 2.309, 147.0,  13.835, 12.269,145.0),
    "3/4-10 UNC":   (19.050, 2.540, 216.0,  16.662, 14.785,215.0),
    "7/8-9 UNC":    (22.225, 2.822, 298.0,  19.480, 17.299,295.0),
    "1-8 UNC":      (25.400, 3.175, 391.0,  22.298, 19.812,390.0),
}

# Combine all
BOLT_LIBRARY: Dict[str, Dict] = {}

def _add_entries(source: Dict[str, tuple], standard: str) -> None:
    for desig, (d, p, A_s, d2, d3, A_bear) in source.items():
        BOLT_LIBRARY[desig] = dict(
            standard=standard,
            designation=desig,
            nominal_diameter=d,
            pitch=p,
            stress_area=A_s,
            head_bearing_area=A_bear,
            minor_diameter=d3,
            pitch_diameter=d2,
        )

_add_entries(_ISO_METRIC_COARSE, "ISO metric")
_add_entries(_ISO_METRIC_FINE, "ISO metric fine")
_add_entries(_UNIFIED, "Unified")


def get_bolt_geometry(
    designation: str,
    shank_length: float = 20.0,
    threaded_length: float = 10.0,
) -> BoltGeometry:
    """Return a BoltGeometry populated from the library for the given designation.

    Args:
        designation: Bolt designation string, e.g. "M12" or "3/8-16 UNC".
        shank_length: Unthreaded shank length [mm] (user-supplied).
        threaded_length: Threaded engagement length [mm] (user-supplied).

    Returns:
        BoltGeometry instance.

    Raises:
        KeyError: If designation not found in library.
    """
    if designation not in BOLT_LIBRARY:
        available = ", ".join(sorted(BOLT_LIBRARY.keys()))
        raise KeyError(f"Bolt '{designation}' not in library. Available: {available}")
    entry = BOLT_LIBRARY[designation]
    return BoltGeometry(
        standard=entry["standard"],
        designation=designation,
        nominal_diameter=entry["nominal_diameter"],
        pitch=entry["pitch"],
        stress_area=entry["stress_area"],
        head_bearing_area=entry["head_bearing_area"],
        shank_length=shank_length,
        threaded_length=threaded_length,
        minor_diameter=entry["minor_diameter"],
        pitch_diameter=entry["pitch_diameter"],
    )

"""ISO Metric and Unified bolt property tables.

Sources:
  ISO 898-1:2013 — Mechanical properties of fasteners — bolts, screws and studs
  ISO 724:1993   — ISO general-purpose metric screw threads
  ISO 273:1979   — Clearance holes for bolts and screws (medium series)
  ISO 4014/4017  — Hexagon head bolts (washer face diameter d_w, minimum)
  ASME B1.1-2003 — Unified inch screw threads

All dimensions in mm. Stress areas per ISO 898-1 Annex B / ASME B1.1.

Tensile stress area formulas:
  ISO:     A_s = π/4 · ((d2 + d3) / 2)²
           d2 = d - 0.6495 · p,  d3 = d - 1.2269 · p
  Unified: A_s = 0.7854 · (d - 0.9743 / n)²   [in²], n = threads per inch

Head bearing area: A_p = π/4 · (d_w² - d_h²) with d_w from ISO 4014 (min
washer face) and d_h the ISO 273 medium clearance hole.  For Unified sizes
the fallbacks d_w ≈ 1.4·d and d_h ≈ 1.06·d are used (documented estimate).
"""
from __future__ import annotations
import math
from typing import Dict, Optional
from boltsizer.models.bolt import BoltGeometry

# ---------------------------------------------------------------------------
# ISO Metric bolt table — coarse pitch (ISO 261 preferred series)
# Fields: (nominal_d, pitch, stress_area, pitch_diam d2, minor_diam d3,
#          washer_face d_w [ISO 4014 min], clearance_hole d_h [ISO 273 medium])
# ---------------------------------------------------------------------------
_ISO_METRIC_COARSE: Dict[str, tuple] = {
    #  desig :  d      p      A_s    d2      d3      d_w    d_h
    "M3":    (3.0,   0.50,   5.03,  2.675,  2.387,  4.57,  3.4),
    "M4":    (4.0,   0.70,   8.78,  3.545,  3.141,  5.88,  4.5),
    "M5":    (5.0,   0.80,  14.20,  4.480,  4.019,  6.88,  5.5),
    "M6":    (6.0,   1.00,  20.10,  5.350,  4.773,  8.88,  6.6),
    "M8":    (8.0,   1.25,  36.60,  7.188,  6.466, 11.63,  9.0),
    "M10":   (10.0,  1.50,  58.00,  9.026,  8.160, 14.63, 11.0),
    "M12":   (12.0,  1.75,  84.30, 10.863,  9.853, 16.63, 13.5),
    "M14":   (14.0,  2.00, 115.0,  12.701, 11.546, 19.64, 15.5),
    "M16":   (16.0,  2.00, 157.0,  14.701, 13.546, 22.49, 17.5),
    "M18":   (18.0,  2.50, 192.0,  16.376, 14.933, 24.85, 20.0),
    "M20":   (20.0,  2.50, 245.0,  18.376, 16.933, 28.19, 22.0),
    "M22":   (22.0,  2.50, 303.0,  20.376, 18.933, 31.71, 24.0),
    "M24":   (24.0,  3.00, 353.0,  22.051, 20.320, 33.61, 26.0),
    "M27":   (27.0,  3.00, 459.0,  25.051, 23.320, 38.00, 30.0),
    "M30":   (30.0,  3.50, 561.0,  27.727, 25.706, 42.75, 33.0),
    "M36":   (36.0,  4.00, 817.0,  33.402, 31.093, 51.11, 39.0),
}

# ISO Metric — fine pitch selected sizes (designation = "MXxY" e.g. "M10x1.25")
# d_w / d_h same as the corresponding coarse nominal size.
_ISO_METRIC_FINE: Dict[str, tuple] = {
    "M8x1":      (8.0,  1.00,  39.17,  7.350,  6.773, 11.63,  9.0),
    "M10x1.25":  (10.0, 1.25,  61.20,  9.188,  8.466, 14.63, 11.0),
    "M10x1":     (10.0, 1.00,  64.50,  9.350,  8.773, 14.63, 11.0),
    "M12x1.5":   (12.0, 1.50,  88.10, 11.026, 10.160, 16.63, 13.5),
    "M12x1.25":  (12.0, 1.25,  92.10, 11.188, 10.466, 16.63, 13.5),
    "M16x1.5":   (16.0, 1.50, 167.0,  15.026, 14.160, 22.49, 17.5),
    "M20x1.5":   (20.0, 1.50, 272.0,  19.026, 18.160, 28.19, 22.0),
    "M24x2":     (24.0, 2.00, 384.0,  22.701, 21.546, 33.61, 26.0),
}

# Unified (UNC/UNF) bolt table — dimensions converted to mm
# pitch = 25.4 / TPI.  A_s = 0.7854·(d - 0.9743/n)² [in²] × 645.16.
# d_w = 0 and d_h = 0 → BoltGeometry fallbacks (1.4·d / 1.06·d).
_UNIFIED: Dict[str, tuple] = {
    #  desig             d_mm    p_mm    A_s_mm2  d2_mm   d3_mm   d_w  d_h
    # d2 = d − 0.6495·p; d3 = d − 1.2269·p (60° thread relations; slightly
    # conservative vs the UN flat/rounded root). A_s per ASME B1.1.
    "1/4-20 UNC":   (  6.350, 1.270,   20.53,   5.525,   4.792,  0.0, 0.0),
    "1/4-28 UNF":   (  6.350, 0.907,   23.47,   5.761,   5.237,  0.0, 0.0),
    "5/16-18 UNC":  (  7.938, 1.411,   33.83,   7.021,   6.206,  0.0, 0.0),
    "5/16-24 UNF":  (  7.938, 1.058,   37.46,   7.250,   6.639,  0.0, 0.0),
    "3/8-16 UNC":   (  9.525, 1.587,   49.99,   8.494,   7.577,  0.0, 0.0),
    "3/8-24 UNF":   (  9.525, 1.058,   56.66,   8.838,   8.227,  0.0, 0.0),
    "7/16-14 UNC":  ( 11.112, 1.814,   68.59,   9.934,   8.887,  0.0, 0.0),
    "1/2-13 UNC":   ( 12.700, 1.954,   91.55,  11.431,  10.303,  0.0, 0.0),
    "1/2-20 UNF":   ( 12.700, 1.270,  103.20,  11.875,  11.142,  0.0, 0.0),
    "9/16-12 UNC":  ( 14.287, 2.117,  117.38,  12.913,  11.691,  0.0, 0.0),
    "5/8-11 UNC":   ( 15.875, 2.309,  145.81,  14.375,  13.042,  0.0, 0.0),
    "3/4-10 UNC":   ( 19.050, 2.540,  215.78,  17.400,  15.934,  0.0, 0.0),
    "7/8-9 UNC":    ( 22.225, 2.822,  297.89,  20.392,  18.762,  0.0, 0.0),
    "1-8 UNC":      ( 25.400, 3.175,  390.80,  23.338,  21.505,  0.0, 0.0),
}

# Combine all
BOLT_LIBRARY: Dict[str, Dict] = {}

def _add_entries(source: Dict[str, tuple], standard: str) -> None:
    for desig, (d, p, A_s, d2, d3, d_w, d_h) in source.items():
        d_w_eff = d_w if d_w > 0 else 1.4 * d
        d_h_eff = d_h if d_h > 0 else 1.06 * d
        BOLT_LIBRARY[desig] = dict(
            standard=standard,
            designation=desig,
            nominal_diameter=d,
            pitch=p,
            stress_area=A_s,
            head_bearing_area=math.pi / 4 * (d_w_eff ** 2 - d_h_eff ** 2),
            minor_diameter=d3,
            pitch_diameter=d2,
            head_bearing_diameter=d_w_eff,
            hole_diameter=d_h_eff,
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
        head_bearing_diameter=entry["head_bearing_diameter"],
        hole_diameter=entry["hole_diameter"],
    )

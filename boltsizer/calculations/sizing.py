"""Sizing helpers: torque-window sweep and bolt auto-suggestion.

The torque window answers "what torque can I spec?":
sweep the assembly torque, evaluate every margin at each point (worst
across load cases), and find the band where all margins are positive.
The floor of the band is set by the minimum-preload checks (separation,
slip, fatigue), the ceiling by the maximum-preload checks (assembly
yield/ultimate, surface pressure).

The bolt suggestion iterates the library for the current joint and
loads: a candidate "passes" if a non-empty torque window exists; the
recommended torque is the point of maximum worst-margin inside it.

All functions are pure and reuse the standard analysis orchestrator.
"""
from __future__ import annotations
import math
from dataclasses import replace
from typing import Dict, List, Literal, Optional

from boltsizer.models.bolt import Bolt
from boltsizer.models.joint import BoltCircle, ClampedInterface, ExternalLoading
from boltsizer.calculations.vdi2230 import run_vdi2230_analysis
from boltsizer.standards.bolt_library import BOLT_LIBRARY, get_bolt_geometry


def _worst_margins_at(
    bolt_circle: BoltCircle,
    interface: ClampedInterface,
    load_cases: List[ExternalLoading],
    torque: float,
    analysis_kwargs: dict,
) -> Dict[str, float]:
    """Run the analysis at a given torque; return check → worst MS across cases."""
    bc = replace(bolt_circle, assembly_torque=torque, target_preload=0.0)
    results = run_vdi2230_analysis(bc, interface, load_cases, **analysis_kwargs)
    worst: Dict[str, float] = {}
    for case in results.case_results:
        for m in case.margins:
            v = m.value
            if m.check_name not in worst or v < worst[m.check_name]:
                worst[m.check_name] = v
    return worst


def torque_window(
    bolt_circle: BoltCircle,
    interface: ClampedInterface,
    load_cases: List[ExternalLoading],
    torque_min: Optional[float] = None,
    torque_max: Optional[float] = None,
    points: int = 60,
    **analysis_kwargs,
) -> dict:
    """Sweep the assembly torque and locate the allowable band.

    Args:
        bolt_circle / interface / load_cases: joint definition (the
            bolt_circle's own assembly_torque only seeds the default range).
        torque_min / torque_max: sweep bounds [N·mm]. Defaults: an
            auto-range reaching from near zero up to the torque that puts
            the maximum preload at roughly the bolt's proof capability.
        points: sweep resolution.
        **analysis_kwargs: forwarded to run_vdi2230_analysis (standard,
            FoS values, tapped params, ...).

    Returns:
        dict with:
          points:      [{torque, min_ms, governing, margins{check: ms}}]
          window:      {t_lo, t_hi} of the widest passing band, or None
          recommended: {torque, min_ms, governing} at max worst-margin
                       inside the window, or None
    """
    bolt = bolt_circle.bolt
    d = bolt.geometry.nominal_diameter
    K = bolt_circle.nut_factor_K

    if torque_max is None:
        # Torque that would put the SCATTER-MAX preload at ~proof capability
        sigma_ref = bolt.material.proof_load_stress or bolt.material.yield_strength
        F_cap = sigma_ref * bolt.geometry.stress_area
        torque_max = 1.3 * F_cap * K * d / 1.25  # headroom past the ceiling
    if torque_min is None:
        torque_min = 0.05 * torque_max
    if points < 5:
        points = 5

    sweep: List[dict] = []
    for i in range(points):
        t = torque_min + (torque_max - torque_min) * i / (points - 1)
        worst = _worst_margins_at(bolt_circle, interface, load_cases, t, analysis_kwargs)
        finite = {k: v for k, v in worst.items() if v != float("inf")}
        governing = min(finite, key=finite.get) if finite else ""
        min_ms = finite[governing] if finite else float("inf")
        sweep.append({
            "torque": t,
            "min_ms": min_ms,
            "governing": governing,
            "margins": finite,
        })

    # Widest contiguous passing band
    best_run: Optional[tuple] = None
    run_start = None
    for i, pt in enumerate(sweep):
        if pt["min_ms"] >= 0:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None:
                if best_run is None or (i - run_start) > (best_run[1] - best_run[0]):
                    best_run = (run_start, i)
                run_start = None
    if run_start is not None:
        if best_run is None or (len(sweep) - run_start) > (best_run[1] - best_run[0]):
            best_run = (run_start, len(sweep))

    window = None
    recommended = None
    if best_run is not None:
        lo, hi = best_run
        band = sweep[lo:hi]
        window = {"t_lo": band[0]["torque"], "t_hi": band[-1]["torque"]}
        best = max(band, key=lambda p: p["min_ms"])
        recommended = {
            "torque": best["torque"],
            "min_ms": best["min_ms"],
            "governing": best["governing"],
        }

    return {"points": sweep, "window": window, "recommended": recommended}


def suggest_bolts(
    bolt_circle: BoltCircle,
    interface: ClampedInterface,
    load_cases: List[ExternalLoading],
    points: int = 30,
    max_candidates: int = 24,
    **analysis_kwargs,
) -> List[dict]:
    """Evaluate every library bolt of the same thread standard for this joint.

    Each candidate keeps the current material grade, coating K values and
    all joint parameters; only the geometry changes.  A candidate passes
    when a non-empty torque window exists.

    Returns a list (ascending nominal diameter):
        {designation, d, A_s, passes, window, recommended, best_min_ms,
         governing}
    """
    current = BOLT_LIBRARY.get(bolt_circle.bolt.geometry.designation)
    family = current["standard"] if current else "ISO metric"
    # Treat coarse+fine metric as one family for suggestions
    families = {"ISO metric", "ISO metric fine"} if family.startswith("ISO") else {family}

    candidates = sorted(
        (e for e in BOLT_LIBRARY.values() if e["standard"] in families),
        key=lambda e: (e["nominal_diameter"], e["pitch"] * -1),
    )[:max_candidates]

    out: List[dict] = []
    base_geom = bolt_circle.bolt.geometry
    for entry in candidates:
        geom = get_bolt_geometry(
            entry["designation"],
            shank_length=base_geom.shank_length,
            threaded_length=base_geom.threaded_length,
        )
        cand_bolt = replace(bolt_circle.bolt, geometry=geom)
        cand_circle = replace(bolt_circle, bolt=cand_bolt)
        win = torque_window(
            cand_circle, interface, load_cases, points=points, **analysis_kwargs,
        )
        best_pt = max(win["points"], key=lambda p: p["min_ms"]) if win["points"] else None
        out.append({
            "designation": entry["designation"],
            "d": entry["nominal_diameter"],
            "A_s": entry["stress_area"],
            "passes": win["window"] is not None,
            "window": win["window"],
            "recommended": win["recommended"],
            "best_min_ms": best_pt["min_ms"] if best_pt else None,
            "governing": (win["recommended"] or best_pt or {}).get("governing", ""),
        })
    return out

"""Tests for the sizing helpers (torque window, bolt suggestion)."""
import math
import pytest
from boltsizer.models.bolt import Bolt
from boltsizer.models.joint import BoltCircle, ClampedLayer, ClampedInterface, ExternalLoading
from boltsizer.standards import get_bolt_geometry, get_material
from boltsizer.calculations.sizing import torque_window, suggest_bolts


def _setup():
    geom = get_bolt_geometry("M12", 20.0, 15.0)
    mat = get_material("ISO 10.9", 12.0)
    bolt = Bolt(geom, mat, "ISO 10.9")
    bc = BoltCircle(
        8, 100.0, bolt, 0.16,
        nut_factor_K_min=0.14, nut_factor_K_max=0.18,
        tool_scatter_pct=0.05, assembly_torque=85000,
    )
    iface = ClampedInterface(
        0, [ClampedLayer("Steel (carbon)", 20.0, 210000)] * 2, "bare", 0.12)
    lcs = [ExternalLoading(axial_force=10000, bending_moment=0,
                           shear_force=5000, load_factor=1.5)]
    return bc, iface, lcs


class TestTorqueWindow:
    def test_window_exists_and_is_consistent(self):
        bc, iface, lcs = _setup()
        win = torque_window(bc, iface, lcs, plate_yield_strength=355.0, points=40)
        assert win["window"] is not None
        assert win["recommended"] is not None
        w, r = win["window"], win["recommended"]
        assert w["t_lo"] < r["torque"] < w["t_hi"]
        assert r["min_ms"] > 0
        # Every sweep point inside the window passes; outside-band edges fail
        for p in win["points"]:
            if w["t_lo"] <= p["torque"] <= w["t_hi"]:
                assert p["min_ms"] >= 0

    def test_floor_and_ceiling_physics(self):
        """Below the window the min-preload checks govern; above it the
        max-preload checks govern."""
        bc, iface, lcs = _setup()
        win = torque_window(bc, iface, lcs, plate_yield_strength=355.0, points=60)
        w = win["window"]
        below = [p for p in win["points"] if p["torque"] < w["t_lo"]]
        above = [p for p in win["points"] if p["torque"] > w["t_hi"]]
        assert below and above
        floor_checks = {"Interface Slip", "Joint Separation", "Fatigue (Infinite Life)"}
        ceiling_checks = {"Yield at Assembly", "Ultimate at Assembly",
                          "Surface Pressure (Head)", "Yield (Working Load)"}
        assert below[-1]["governing"] in floor_checks, below[-1]["governing"]
        assert above[0]["governing"] in ceiling_checks, above[0]["governing"]

    def test_impossible_joint_returns_no_window(self):
        bc, iface, lcs = _setup()
        # Absurd shear load no torque can carry via friction
        lcs = [ExternalLoading(axial_force=10000, bending_moment=0,
                               shear_force=5e6, load_factor=1.5)]
        win = torque_window(bc, iface, lcs, plate_yield_strength=355.0, points=30)
        assert win["window"] is None
        assert win["recommended"] is None


class TestSuggestBolts:
    def test_monotonic_pass_boundary(self):
        """Small sizes fail, larger sizes pass; candidates ascend by diameter."""
        bc, iface, lcs = _setup()
        out = suggest_bolts(bc, iface, lcs, points=20, plate_yield_strength=355.0)
        assert len(out) > 8
        diameters = [c["d"] for c in out]
        assert diameters == sorted(diameters)
        by_desig = {c["designation"]: c for c in out}
        assert not by_desig["M3"]["passes"]
        assert by_desig["M12"]["passes"]
        # Passing candidates carry a torque recommendation inside their window
        for c in out:
            if c["passes"]:
                assert c["recommended"] is not None
                assert c["window"]["t_lo"] <= c["recommended"]["torque"] <= c["window"]["t_hi"]

    def test_same_family_only(self):
        bc, iface, lcs = _setup()
        out = suggest_bolts(bc, iface, lcs, points=15, plate_yield_strength=355.0)
        assert all(not c["designation"].endswith("UNC") for c in out)

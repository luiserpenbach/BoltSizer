"""Tests for Wave 4 depth features: eccentric model, patterns, sensitivity."""
import math
import pytest
from dataclasses import replace
from boltsizer.models.bolt import Bolt
from boltsizer.models.joint import BoltCircle, ClampedLayer, ClampedInterface, ExternalLoading
from boltsizer.standards import get_bolt_geometry, get_material
from boltsizer.calculations.joint_stiffness import calculate_joint_stiffness
from boltsizer.calculations.load_distribution import calculate_load_distribution
from boltsizer.calculations.sizing import sensitivity


def _bc(**kw):
    geom = get_bolt_geometry("M12", 20.0, 15.0)
    mat = get_material("ISO 10.9", 12.0)
    bolt = Bolt(geom, mat, "ISO 10.9")
    defaults = dict(num_bolts=8, bolt_circle_diameter=100.0, bolt=bolt,
                    nut_factor_K=0.16, assembly_torque=40000)
    defaults.update(kw)
    return BoltCircle(**defaults)


def _iface(**kw):
    return ClampedInterface(
        0, [ClampedLayer("Steel (carbon)", 20.0, 210000)] * 2,
        "bare", 0.12, **kw)


class TestEccentricModel:
    def test_zero_eccentricity_matches_concentric(self):
        r0 = calculate_joint_stiffness(_bc(), _iface())
        r1 = calculate_joint_stiffness(_bc(), _iface(eccentricity_s=0.0, load_eccentricity_a=0.0))
        assert math.isclose(r0.phi_basic, r1.phi_basic, rel_tol=1e-12)
        assert r1.phi_concentric is None

    def test_eccentric_load_raises_bolt_share(self):
        """a > s > 0 (load further out than the bolt) → prying → higher Φ."""
        r0 = calculate_joint_stiffness(_bc(), _iface())
        r1 = calculate_joint_stiffness(_bc(), _iface(eccentricity_s=5.0, load_eccentricity_a=15.0))
        assert r1.phi_basic > r0.phi_basic
        assert r1.phi_concentric == pytest.approx(r0.phi_basic)

    def test_eccentric_clamping_alone_lowers_bolt_share(self):
        """s > 0, a = 0: the tilting clamp solid takes more of the load."""
        r0 = calculate_joint_stiffness(_bc(), _iface())
        r1 = calculate_joint_stiffness(_bc(), _iface(eccentricity_s=8.0, load_eccentricity_a=0.0))
        assert r1.phi_basic < r0.phi_basic

    def test_phi_clamped_to_unity(self):
        r = calculate_joint_stiffness(
            _bc(), _iface(eccentricity_s=5.0, load_eccentricity_a=500.0))
        assert 0.0 <= r.phi_basic <= 1.0


class TestPatterns:
    def test_circle_matches_legacy_closed_form(self):
        bc = _bc(num_bolts=8, bolt_circle_diameter=100.0)
        lc = ExternalLoading(axial_force=0, bending_moment=500000, shear_force=0)
        r = calculate_load_distribution(bc, lc)
        assert math.isclose(r.F_total_axial, 2 * 500000 / (8 * 50.0), rel_tol=1e-9)

    def test_rectangle_bending_distribution(self):
        """2×2 grid, pitch 80: under pure bending each outer bolt carries
        M·x/Σx² with x = ±40 → F = M·40/(4·40²)."""
        bc = _bc(pattern="rectangle", rect_nx=2, rect_ny=2,
                 rect_pitch_x=80.0, rect_pitch_y=60.0)
        M = 400000.0
        lc = ExternalLoading(axial_force=0, bending_moment=M, shear_force=0)
        r = calculate_load_distribution(bc, lc)
        assert len(r.bolt_axial_forces) == 4
        assert math.isclose(r.F_total_axial, M * 40.0 / (4 * 40.0 ** 2), rel_tol=1e-9)
        # Symmetric: sum of bending forces = 0
        assert math.isclose(sum(r.bolt_axial_forces), 0.0, abs_tol=1e-6)

    def test_custom_positions_centroid_correction(self):
        """Custom positions are re-centred on the centroid."""
        bc = _bc(pattern="custom",
                 custom_positions=[(0.0, 0.0), (100.0, 0.0)])
        lc = ExternalLoading(axial_force=1000, bending_moment=0, shear_force=0)
        r = calculate_load_distribution(bc, lc)
        assert [p[0] for p in r.bolt_positions] == [-50.0, 50.0]
        assert all(math.isclose(f, 500.0) for f in r.bolt_axial_forces)

    def test_torsion_general_pattern(self):
        """Torsion shear = M_T·r_max/Σr² (reduces to M_T/(n·r) on a circle)."""
        bc = _bc(pattern="rectangle", rect_nx=2, rect_ny=2,
                 rect_pitch_x=60.0, rect_pitch_y=60.0)
        lc = ExternalLoading(axial_force=0, bending_moment=0, shear_force=0,
                             torsion=180000)
        r = calculate_load_distribution(bc, lc)
        r_i = math.hypot(30.0, 30.0)
        assert math.isclose(r.V_torsion_per_bolt, 180000 * r_i / (4 * r_i ** 2), rel_tol=1e-9)


class TestSensitivity:
    def test_ranked_and_consistent(self):
        bc = _bc(nut_factor_K_min=0.14, nut_factor_K_max=0.18, tool_scatter_pct=0.05)
        lcs = [ExternalLoading(axial_force=10000, bending_moment=0,
                               shear_force=5000, load_factor=1.5)]
        out = sensitivity(bc, _iface(), lcs, plate_yield_strength=355.0)
        assert "baseline_ms" in out and len(out["params"]) >= 4
        swings = [abs(p["high_ms"] - p["low_ms"]) for p in out["params"]]
        assert swings == sorted(swings, reverse=True)
        # Higher friction must help (or at least not hurt) the worst margin
        mu = next(p for p in out["params"] if "friction" in p["name"])
        assert mu["high_ms"] >= mu["low_ms"]

    def test_thermal_param_only_with_dT(self):
        bc = _bc()
        lcs = [ExternalLoading(axial_force=10000, bending_moment=0, shear_force=1000)]
        out = sensitivity(bc, _iface(), lcs, plate_yield_strength=355.0)
        assert not any("ΔT" in p["name"] for p in out["params"])

"""Tests for boltsizer.calculations.preload module."""
import json
import math
import pathlib
import pytest
from boltsizer.models.bolt import BoltGeometry, BoltMaterial, Bolt
from boltsizer.models.joint import BoltCircle, ClampedLayer, ClampedInterface
from boltsizer.calculations.preload import calculate_preload

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _make_bolt_circle(
    designation="M12",
    grade="ISO 8.8",
    K=0.16,
    torque_Nmm=85000,
    method="torque_wrench",
    num_surfaces=2,
    rz=6.3,
    shank=20.0,
    thread=15.0,
) -> BoltCircle:
    """Helper: build a minimal BoltCircle for testing."""
    from boltsizer.standards import get_bolt_geometry, get_material
    geom = get_bolt_geometry(designation, shank_length=shank, threaded_length=thread)
    mat = get_material(grade)
    bolt = Bolt(geometry=geom, material=mat, grade=grade)
    return BoltCircle(
        num_bolts=1,
        bolt_circle_diameter=0.0,
        bolt=bolt,
        nut_factor_K=K,
        assembly_torque=torque_Nmm,
        tightening_method=method,
        num_mating_surfaces=num_surfaces,
        surface_roughness_Rz=rz,
    )


class TestTorqueToPreload:
    """VDI 2230 Eq. (5.1): F_M = M_A / (K · d)"""

    def test_nominal_preload_formula(self):
        """Check F_M = M_A / (K · d) for known values."""
        bc = _make_bolt_circle(designation="M12", K=0.16, torque_Nmm=85000)
        grip = 40.0
        result = calculate_preload(bc, grip)
        expected = 85000 / (0.16 * 12.0)
        assert math.isclose(result.F_M_nominal, expected, rel_tol=1e-6), (
            f"Expected {expected:.1f} N, got {result.F_M_nominal:.1f} N"
        )

    def test_direct_preload_mode(self):
        """Direct preload entry mode bypasses K·d calculation."""
        from boltsizer.standards import get_bolt_geometry, get_material
        geom = get_bolt_geometry("M10", shank_length=15.0, threaded_length=12.0)
        mat = get_material("ISO 8.8")
        bolt = Bolt(geometry=geom, material=mat, grade="ISO 8.8")
        bc = BoltCircle(
            num_bolts=1,
            bolt_circle_diameter=0.0,
            bolt=bolt,
            nut_factor_K=0.20,
            assembly_torque=0.0,
            target_preload=30000.0,
            tightening_method="torque_wrench",
        )
        result = calculate_preload(bc, 30.0)
        assert math.isclose(result.F_M_nominal, 30000.0, rel_tol=1e-9)

    def test_vdi_example1_fixture(self):
        """Verify nominal preload against VDI 2230 Example 1 fixture."""
        data = json.loads((FIXTURES / "vdi2230_example1.json").read_text())
        expected_F_M = data["expected"]["F_M_nominal_approx"]
        bc = _make_bolt_circle(
            designation=data["bolt"]["designation"],
            grade=data["bolt"]["grade"],
            K=data["bolt_circle"]["nut_factor_K"],
            torque_Nmm=data["bolt_circle"]["assembly_torque"],
            method=data["bolt_circle"]["tightening_method"],
            num_surfaces=data["bolt_circle"]["num_mating_surfaces"],
            rz=data["bolt_circle"]["surface_roughness_Rz"],
            shank=data["bolt"]["shank_length"],
            thread=data["bolt"]["threaded_length"],
        )
        grip = sum(l["thickness"] for l in data["interface"]["layers"])
        result = calculate_preload(bc, grip)
        assert math.isclose(result.F_M_nominal, expected_F_M, rel_tol=0.01), (
            f"Fixture mismatch: expected ~{expected_F_M} N, got {result.F_M_nominal:.1f} N"
        )


class TestScatter:
    """VDI 2230 Table A5 scatter factor tests."""

    def test_torque_wrench_alpha_A(self):
        bc = _make_bolt_circle(method="torque_wrench")
        result = calculate_preload(bc, 40.0)
        assert math.isclose(result.alpha_A, 1.60, rel_tol=1e-6)

    def test_hydraulic_smaller_scatter(self):
        bc_torque = _make_bolt_circle(method="torque_wrench")
        bc_hydraulic = _make_bolt_circle(method="hydraulic_tensioning")
        r_t = calculate_preload(bc_torque, 40.0)
        r_h = calculate_preload(bc_hydraulic, 40.0)
        assert r_h.alpha_A < r_t.alpha_A, "Hydraulic should have less scatter than torque wrench"

    def test_min_preload_less_than_max(self):
        bc = _make_bolt_circle()
        result = calculate_preload(bc, 40.0)
        assert result.F_M_min < result.F_M_max

    def test_min_max_ratio_equals_alpha(self):
        bc = _make_bolt_circle(method="torque_wrench")
        result = calculate_preload(bc, 40.0)
        ratio = result.F_M_max / result.F_M_min
        assert math.isclose(ratio, result.alpha_A, rel_tol=1e-6)


class TestEmbedding:
    """Embedding relaxation — VDI 2230 Table 5.4."""

    def test_embedding_positive(self):
        bc = _make_bolt_circle(num_surfaces=2, rz=6.3)
        result = calculate_preload(bc, 40.0)
        assert result.F_Z > 0

    def test_more_interfaces_more_relaxation(self):
        bc1 = _make_bolt_circle(num_surfaces=1)
        bc2 = _make_bolt_circle(num_surfaces=4)
        r1 = calculate_preload(bc1, 40.0)
        r2 = calculate_preload(bc2, 40.0)
        assert r2.F_Z > r1.F_Z

    def test_net_preload_min_less_than_scatter_min(self):
        bc = _make_bolt_circle()
        result = calculate_preload(bc, 40.0)
        assert result.F_preload_min <= result.F_M_min

    def test_net_preload_non_negative(self):
        """Even with extreme embedding, net preload should be clamped to zero."""
        # Very short grip → high F_Z
        bc = _make_bolt_circle(num_surfaces=5, rz=40.0)
        result = calculate_preload(bc, 1.0)  # Very short grip
        assert result.F_preload_min >= 0.0

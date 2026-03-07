"""Tests for boltsizer.calculations.load_distribution module."""
import math
import pytest
from boltsizer.models.bolt import Bolt
from boltsizer.models.joint import BoltCircle, ExternalLoading
from boltsizer.calculations.load_distribution import calculate_load_distribution


def _make_bolt_circle(n_bolts: int = 8, pcd: float = 100.0) -> BoltCircle:
    from boltsizer.standards import get_bolt_geometry, get_material
    geom = get_bolt_geometry("M10", shank_length=15.0, threaded_length=12.0)
    mat = get_material("ISO 10.9")
    bolt = Bolt(geometry=geom, material=mat, grade="ISO 10.9")
    return BoltCircle(
        num_bolts=n_bolts,
        bolt_circle_diameter=pcd,
        bolt=bolt,
        nut_factor_K=0.13,
        assembly_torque=50000,
    )


class TestAxialDistribution:
    """Axial load should be shared equally among bolts."""

    def test_pure_axial_equal_share(self):
        bc = _make_bolt_circle(n_bolts=8)
        lc = ExternalLoading(axial_force=16000, bending_moment=0, shear_force=0)
        result = calculate_load_distribution(bc, lc)
        for f in result.bolt_axial_forces:
            assert math.isclose(f, 2000.0, rel_tol=1e-9)

    def test_load_factor_applied(self):
        bc = _make_bolt_circle(n_bolts=4)
        lc = ExternalLoading(axial_force=8000, bending_moment=0, shear_force=0, load_factor=1.25)
        result = calculate_load_distribution(bc, lc)
        expected_per_bolt = 8000 * 1.25 / 4
        for f in result.bolt_axial_forces:
            assert math.isclose(f, expected_per_bolt, rel_tol=1e-9)


class TestBendingDistribution:
    """Bending moment should add/subtract linearly from bolt loads."""

    def test_bending_symmetric_sum_zero(self):
        """Sum of bending contributions must equal zero for symmetric pattern."""
        bc = _make_bolt_circle(n_bolts=8)
        lc = ExternalLoading(axial_force=0, bending_moment=500000, shear_force=0)
        result = calculate_load_distribution(bc, lc)
        # Sum of all bolt forces should be approximately zero (no net axial)
        total = sum(result.bolt_axial_forces)
        assert math.isclose(total, 0.0, abs_tol=1e-3)

    def test_critical_bolt_at_zero_degrees(self):
        """With bending about horizontal axis, bolt at 0° (cos=1) should be critical."""
        bc = _make_bolt_circle(n_bolts=4)
        lc = ExternalLoading(axial_force=0, bending_moment=100000, shear_force=0)
        result = calculate_load_distribution(bc, lc)
        # The bolt at index 0 (θ=0°, cos(0)=1) should have highest tension
        assert result.critical_bolt_index == 0

    def test_combined_axial_bending(self):
        """Combined loading: critical bolt has axial + bending contributions."""
        bc = _make_bolt_circle(n_bolts=8, pcd=100.0)
        lc = ExternalLoading(axial_force=8000, bending_moment=200000, shear_force=0)
        result = calculate_load_distribution(bc, lc)
        crit = result.critical_bolt_index
        assert result.bolt_axial_forces[crit] == max(result.bolt_axial_forces)
        assert result.F_total_axial == result.bolt_axial_forces[crit]

    def test_ecss_reference_fixture(self):
        """Verify against ECSS reference fixture."""
        import json, pathlib
        fixture = pathlib.Path(__file__).parent / "fixtures" / "ecss_reference_case.json"
        data = json.loads(fixture.read_text())
        bc = _make_bolt_circle(
            n_bolts=data["bolt_circle"]["num_bolts"],
            pcd=data["bolt_circle"]["bolt_circle_diameter"],
        )
        lc_data = data["loading"]
        lc = ExternalLoading(
            axial_force=lc_data["axial_force"],
            bending_moment=lc_data["bending_moment"],
            shear_force=lc_data["shear_force"],
            load_factor=lc_data["load_factor"],
            case_name=lc_data["case_name"],
        )
        result = calculate_load_distribution(bc, lc)
        # Critical bolt should be at index 0 (bending maximises force there)
        assert result.critical_bolt_index == 0
        # Critical bolt force must exceed pure axial share
        pure_axial = lc_data["axial_force"] * lc_data["load_factor"] / data["bolt_circle"]["num_bolts"]
        assert result.F_total_axial > pure_axial


class TestShearDistribution:
    """Shear is distributed equally."""

    def test_shear_per_bolt_equal(self):
        bc = _make_bolt_circle(n_bolts=6)
        lc = ExternalLoading(axial_force=0, bending_moment=0, shear_force=12000)
        result = calculate_load_distribution(bc, lc)
        assert math.isclose(result.V_shear_per_bolt, 2000.0, rel_tol=1e-9)

    def test_shear_with_load_factor(self):
        bc = _make_bolt_circle(n_bolts=4)
        lc = ExternalLoading(axial_force=0, bending_moment=0, shear_force=4000, load_factor=1.5)
        result = calculate_load_distribution(bc, lc)
        assert math.isclose(result.V_shear_per_bolt, 4000 * 1.5 / 4, rel_tol=1e-9)

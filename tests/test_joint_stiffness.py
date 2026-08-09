"""Tests for boltsizer.calculations.joint_stiffness module."""
import math
import pytest
from boltsizer.models.bolt import BoltGeometry, BoltMaterial, Bolt
from boltsizer.models.joint import BoltCircle, ClampedLayer, ClampedInterface
from boltsizer.calculations.joint_stiffness import calculate_joint_stiffness


def _make_bolt_and_circle(designation="M12", grade="ISO 8.8", shank=20.0, thread=15.0):
    from boltsizer.standards import get_bolt_geometry, get_material
    geom = get_bolt_geometry(designation, shank_length=shank, threaded_length=thread)
    mat = get_material(grade)
    bolt = Bolt(geometry=geom, material=mat, grade=grade)
    bc = BoltCircle(
        num_bolts=4, bolt_circle_diameter=80.0, bolt=bolt,
        nut_factor_K=0.16, assembly_torque=85000,
    )
    return bolt, bc


def _steel_interface(thickness: float = 20.0, n_layers: int = 2) -> ClampedInterface:
    layers = [ClampedLayer("Steel (carbon)", thickness, 210000) for _ in range(n_layers)]
    return ClampedInterface(
        total_clamped_length=thickness * n_layers,
        layers=layers,
        interface_treatment="bare metal",
        friction_coefficient=0.12,
    )


class TestBoltCompliance:
    """δ_S should be positive and physically reasonable."""

    def test_compliance_positive(self):
        _, bc = _make_bolt_and_circle()
        iface = _steel_interface()
        result = calculate_joint_stiffness(bc, iface)
        assert result.delta_S > 0

    def test_more_shank_in_grip_lower_compliance(self):
        """The loaded lengths are reconciled with the grip: a longer shank
        within the same grip replaces thread (A_d3) with shank (A_N > A_d3),
        so the bolt gets STIFFER (lower compliance)."""
        _, bc_short = _make_bolt_and_circle(shank=10.0, thread=10.0)
        _, bc_long = _make_bolt_and_circle(shank=30.0, thread=10.0)
        iface = _steel_interface()
        r_short = calculate_joint_stiffness(bc_short, iface)
        r_long = calculate_joint_stiffness(bc_long, iface)
        assert r_long.delta_S < r_short.delta_S

    def test_longer_grip_higher_compliance(self):
        """A longer grip (thicker stack) increases bolt compliance."""
        _, bc = _make_bolt_and_circle(shank=10.0, thread=10.0)
        r_thin = calculate_joint_stiffness(bc, _steel_interface(thickness=15.0))
        r_thick = calculate_joint_stiffness(bc, _steel_interface(thickness=30.0))
        assert r_thick.delta_S > r_thin.delta_S

    def test_larger_diameter_lower_compliance(self):
        """Larger bolt diameter → larger area → lower compliance."""
        _, bc_small = _make_bolt_and_circle(designation="M8")
        _, bc_large = _make_bolt_and_circle(designation="M16")
        iface = _steel_interface()
        r_small = calculate_joint_stiffness(bc_small, iface)
        r_large = calculate_joint_stiffness(bc_large, iface)
        assert r_small.delta_S > r_large.delta_S


class TestClampedPartCompliance:
    """δ_P should follow physical expectations."""

    def test_compliance_positive(self):
        _, bc = _make_bolt_and_circle()
        iface = _steel_interface()
        result = calculate_joint_stiffness(bc, iface)
        assert result.delta_P > 0

    def test_aluminium_higher_compliance_than_steel(self):
        """Aluminium (E=70 GPa) should be more compliant than steel (E=210 GPa)."""
        _, bc = _make_bolt_and_circle()
        steel_iface = ClampedInterface(
            total_clamped_length=40.0,
            layers=[ClampedLayer("Steel", 20.0, 210000), ClampedLayer("Steel", 20.0, 210000)],
            interface_treatment="bare metal",
            friction_coefficient=0.12,
        )
        al_iface = ClampedInterface(
            total_clamped_length=40.0,
            layers=[ClampedLayer("Al", 20.0, 70000), ClampedLayer("Al", 20.0, 70000)],
            interface_treatment="bare metal",
            friction_coefficient=0.12,
        )
        r_steel = calculate_joint_stiffness(bc, steel_iface)
        r_al = calculate_joint_stiffness(bc, al_iface)
        assert r_al.delta_P > r_steel.delta_P


class TestForceRatio:
    """φ must lie in (0, 1); φ_n = n · φ."""

    def test_phi_in_range(self):
        _, bc = _make_bolt_and_circle()
        iface = _steel_interface()
        result = calculate_joint_stiffness(bc, iface)
        assert 0 < result.phi_basic < 1

    def test_phi_n_equals_n_times_phi(self):
        _, bc = _make_bolt_and_circle()
        iface = _steel_interface()
        n = 0.3
        result = calculate_joint_stiffness(bc, iface, load_intro_factor_n=n)
        assert math.isclose(result.phi_n, n * result.phi_basic, rel_tol=1e-9)

    def test_phi_n_at_zero_n(self):
        """n=0 (load at interface) → φ_n = 0."""
        _, bc = _make_bolt_and_circle()
        iface = _steel_interface()
        result = calculate_joint_stiffness(bc, iface, load_intro_factor_n=0.0)
        assert result.phi_n == 0.0

    def test_phi_n_at_one_n(self):
        """n=1 (load at head) → φ_n = φ_basic."""
        _, bc = _make_bolt_and_circle()
        iface = _steel_interface()
        result = calculate_joint_stiffness(bc, iface, load_intro_factor_n=1.0)
        assert math.isclose(result.phi_n, result.phi_basic, rel_tol=1e-9)

    def test_stiffer_clamped_part_lower_phi(self):
        """With very stiff clamped plates, φ approaches 0 (plates take almost all load)."""
        _, bc = _make_bolt_and_circle(designation="M8")
        rigid_iface = ClampedInterface(
            total_clamped_length=40.0,
            layers=[ClampedLayer("Rigid", 20.0, 10_000_000), ClampedLayer("Rigid", 20.0, 10_000_000)],
            interface_treatment="bare metal",
            friction_coefficient=0.12,
        )
        soft_iface = ClampedInterface(
            total_clamped_length=40.0,
            layers=[ClampedLayer("Soft", 20.0, 10000), ClampedLayer("Soft", 20.0, 10000)],
            interface_treatment="bare metal",
            friction_coefficient=0.12,
        )
        r_rigid = calculate_joint_stiffness(bc, rigid_iface)
        r_soft = calculate_joint_stiffness(bc, soft_iface)
        assert r_rigid.phi_basic < r_soft.phi_basic

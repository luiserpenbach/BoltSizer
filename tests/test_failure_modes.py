"""Tests for boltsizer.calculations.failure_modes module."""
import math
import pytest
from boltsizer.models.bolt import Bolt
from boltsizer.models.joint import BoltCircle, ClampedLayer, ClampedInterface, ExternalLoading
from boltsizer.models.results import PreloadResult, StiffnessResult, LoadDistributionResult
from boltsizer.calculations.failure_modes import (
    check_yield_assembly,
    check_yield_combined,
    check_joint_separation,
    check_slip,
    check_bolt_shear,
    check_bearing,
    check_fatigue,
    calculate_all_margins,
)


def _bolt(designation="M12", grade="ISO 8.8"):
    from boltsizer.standards import get_bolt_geometry, get_material
    geom = get_bolt_geometry(designation, shank_length=20.0, threaded_length=15.0)
    mat = get_material(grade)
    return Bolt(geometry=geom, material=mat, grade=grade)


def _preload(F_M_max=40000, alpha_A=1.6, F_Z=500):
    F_M_min = F_M_max / alpha_A
    return PreloadResult(
        F_M_nominal=F_M_max,
        F_M_max=F_M_max,
        F_M_min=F_M_min,
        F_Z=F_Z,
        F_preload_max=F_M_max,
        F_preload_min=max(0.0, F_M_min - F_Z),
        alpha_A=alpha_A,
        f_Z_displacement=0.005,
    )


def _stiffness(phi_basic=0.1, n=0.5):
    delta_S = 1e-5
    delta_P = delta_S * phi_basic / (1 - phi_basic)
    return StiffnessResult(
        delta_S=delta_S,
        delta_P=delta_P,
        phi_basic=phi_basic,
        phi_n=n * phi_basic,
        load_intro_factor_n=n,
    )


def _load_dist(F_ext=10000, V=5000, crit=0, n_bolts=4):
    axial_each = F_ext / n_bolts
    return LoadDistributionResult(
        critical_bolt_index=crit,
        F_axial_per_bolt=axial_each,
        F_bend_per_bolt=0.0,
        V_shear_per_bolt=V,
        F_total_axial=F_ext,
        bolt_angles_deg=[0.0, 90.0, 180.0, 270.0][:n_bolts],
        bolt_axial_forces=[F_ext] + [0.0] * (n_bolts - 1),
    )


class TestYieldAssembly:
    def test_pass_when_well_below_proof(self):
        bolt = _bolt("M12", "ISO 8.8")
        pre = _preload(F_M_max=30000)
        ms = check_yield_assembly(bolt, pre)
        assert ms.value > 0, f"Expected positive MS, got {ms.value:.3f}"
        assert ms.status in ("PASS", "WARNING")

    def test_fail_when_over_proof(self):
        bolt = _bolt("M12", "ISO 8.8")
        # Force a failure: set F_M_max > 0.9 * proof
        A_s = bolt.geometry.stress_area  # 84.3 mm²
        sigma_proof = bolt.material.proof_load_stress
        F_exceed = 0.95 * A_s * sigma_proof  # Above 90% allowable
        pre = _preload(F_M_max=F_exceed)
        ms = check_yield_assembly(bolt, pre)
        assert ms.value < 0 or ms.status == "FAIL", "Should fail when over 90% proof"

    def test_ms_formula_correct(self):
        """MS = (0.9 * F_proof / F_M_max) - 1"""
        bolt = _bolt("M12", "ISO 8.8")
        A_s = bolt.geometry.stress_area
        sigma_proof = bolt.material.proof_load_stress
        F_proof = A_s * sigma_proof
        F_M_max = 30000
        pre = _preload(F_M_max=F_M_max)
        ms = check_yield_assembly(bolt, pre)
        expected = 0.9 * F_proof / F_M_max - 1
        assert math.isclose(ms.value, expected, rel_tol=1e-6)


class TestJointSeparation:
    def test_no_external_load_infinite_ms(self):
        pre = _preload()
        stiff = _stiffness()
        ms = check_joint_separation(pre, stiff, F_ext=0.0)
        assert ms.value == float("inf") or ms.value > 100

    def test_large_opening_force_fails(self):
        pre = _preload(F_M_max=5000, alpha_A=1.6, F_Z=100)
        stiff = _stiffness(phi_basic=0.1)
        # Opening force >> preload
        ms = check_joint_separation(pre, stiff, F_ext=100000)
        assert ms.value < 0

    def test_ecss_uses_FM_min_not_net(self):
        """ECSS convention uses F_M_min (before embedding), VDI uses F_preload_min."""
        pre = _preload(F_M_max=40000, F_Z=5000)  # Large embedding
        stiff = _stiffness()
        ms_vdi = check_joint_separation(pre, stiff, F_ext=10000, standard="VDI")
        ms_ecss = check_joint_separation(pre, stiff, F_ext=10000, standard="ECSS")
        # ECSS uses higher preload (F_M_min > F_preload_min), so should be more conservative
        # (higher allowable → actually higher MS for ECSS? No — ECSS doesn't subtract F_Z)
        # ECSS: allowable = F_M_min (larger), VDI: allowable = F_preload_min (smaller)
        assert ms_ecss.allowable >= ms_vdi.allowable, (
            "ECSS should use F_M_min (before embedding) as allowable"
        )

    def test_slip_uses_fpreload_min(self):
        """VDI 2230 §5.4.4: slip check must use F_clamp_min = F_V_min - F_ext·(1-φ)."""
        pre = _preload(F_M_max=40000, F_Z=3000)
        stiff = _stiffness(phi_basic=0.15, n=0.5)
        ms = check_slip(pre, 5000, stiff, friction_coeff=0.12, num_friction_interfaces=1, V_shear=3000)
        # Clamp min should be based on F_preload_min (after embedding)
        F_clamp_min = max(0.0, pre.F_preload_min - 5000 * (1 - stiff.phi_n))
        expected_capacity = 0.12 * F_clamp_min * 1
        assert math.isclose(ms.allowable, expected_capacity, rel_tol=1e-6)


class TestSlip:
    def test_slip_check_uses_min_preload(self):
        """Slip check must use F_clamp_min, not F_clamp_max."""
        pre = _preload(F_M_max=50000, alpha_A=1.6, F_Z=2000)
        stiff = _stiffness(phi_basic=0.1, n=0.5)
        F_ext = 5000
        V = 3000
        ms = check_slip(pre, F_ext, stiff, 0.15, 1, V)
        F_clamp_min = max(0.0, pre.F_preload_min - F_ext * (1 - stiff.phi_n))
        expected = 0.15 * F_clamp_min * 1
        assert math.isclose(ms.allowable, expected, rel_tol=1e-6)

    def test_zero_shear_infinite_ms(self):
        pre = _preload()
        stiff = _stiffness()
        ms = check_slip(pre, 0, stiff, 0.15, 1, V_shear=0.0)
        assert ms.value == float("inf") or ms.value > 100


class TestBoltShear:
    def test_zero_shear_infinite_ms(self):
        bolt = _bolt("M12", "ISO 8.8")
        ms = check_bolt_shear(bolt, V_shear=0.0)
        assert ms.value == float("inf") or ms.value > 100

    def test_shear_capacity_formula(self):
        bolt = _bolt("M12", "ISO 8.8")
        A_s = bolt.geometry.stress_area
        sigma_y = bolt.material.yield_strength
        V = 5000
        ms = check_bolt_shear(bolt, V)
        expected = 0.6 * A_s * sigma_y / V - 1
        assert math.isclose(ms.value, expected, rel_tol=1e-6)


class TestFatigue:
    def test_returns_none_for_no_fatigue_limit(self):
        from boltsizer.models.bolt import BoltMaterial
        geom = _bolt().geometry
        mat_no_fatigue = BoltMaterial(name="Custom", yield_strength=800, uts=1000,
                                      youngs_modulus=210000, fatigue_limit=None)
        bolt = Bolt(geometry=geom, material=mat_no_fatigue, grade="Custom")
        stiff = _stiffness()
        result = check_fatigue(bolt, stiff, F_ext_amplitude=5000)
        assert result is None

    def test_fatigue_amplitude_formula(self):
        """F_SA = phi_n * F_ext / 2; MS = sigma_allow / (F_SA/A_s) - 1"""
        bolt = _bolt("M12", "ISO 8.8")
        stiff = _stiffness(phi_basic=0.1, n=0.5)
        F_ext = 10000
        ms = check_fatigue(bolt, stiff, F_ext_amplitude=F_ext)
        F_SA = stiff.phi_n * F_ext / 2
        A_s = bolt.geometry.stress_area
        sigma_a = F_SA / A_s
        sigma_allow = bolt.material.fatigue_limit
        expected = sigma_allow / sigma_a - 1
        assert math.isclose(ms.value, expected, rel_tol=1e-6)


class TestCalculateAllMargins:
    def _make_interface(self):
        layers = [ClampedLayer("Steel", 20.0, 210000), ClampedLayer("Steel", 20.0, 210000)]
        return ClampedInterface(
            total_clamped_length=40.0,
            layers=layers,
            interface_treatment="bare metal",
            friction_coefficient=0.12,
            num_friction_interfaces=1,
        )

    def test_returns_list(self):
        bolt = _bolt("M12", "ISO 8.8")
        pre = _preload()
        stiff = _stiffness()
        ld = _load_dist()
        iface = self._make_interface()
        lc = ExternalLoading(axial_force=10000, bending_moment=0, shear_force=5000)
        margins = calculate_all_margins(bolt, pre, stiff, ld, iface, lc)
        assert len(margins) >= 6

    def test_exactly_one_binding(self):
        bolt = _bolt("M12", "ISO 8.8")
        pre = _preload()
        stiff = _stiffness()
        ld = _load_dist()
        iface = self._make_interface()
        lc = ExternalLoading(axial_force=10000, bending_moment=0, shear_force=5000)
        margins = calculate_all_margins(bolt, pre, stiff, ld, iface, lc)
        binding = [m for m in margins if m.binding]
        assert len(binding) == 1

    def test_binding_is_worst_margin(self):
        bolt = _bolt("M12", "ISO 8.8")
        pre = _preload()
        stiff = _stiffness()
        ld = _load_dist()
        iface = self._make_interface()
        lc = ExternalLoading(axial_force=10000, bending_moment=0, shear_force=5000)
        margins = calculate_all_margins(bolt, pre, stiff, ld, iface, lc)
        binding = next(m for m in margins if m.binding)
        finite_margins = [m.value for m in margins if m.value != float("inf")]
        assert binding.value == min(finite_margins)

    def test_sorted_worst_first(self):
        bolt = _bolt("M12", "ISO 8.8")
        pre = _preload()
        stiff = _stiffness()
        ld = _load_dist()
        iface = self._make_interface()
        lc = ExternalLoading(axial_force=10000, bending_moment=0, shear_force=5000)
        margins = calculate_all_margins(bolt, pre, stiff, ld, iface, lc)
        finite = [m.value for m in margins if m.value != float("inf")]
        assert finite == sorted(finite)

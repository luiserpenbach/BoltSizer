"""Tests for boltsizer.calculations.failure_modes module."""
import math
import pytest
from boltsizer.models.bolt import Bolt, BoltMaterial
from boltsizer.models.joint import BoltCircle, ClampedLayer, ClampedInterface, ExternalLoading
from boltsizer.models.results import PreloadResult, StiffnessResult, LoadDistributionResult
from boltsizer.calculations.failure_modes import (
    check_yield_assembly,
    check_yield_combined,
    check_ultimate_combined,
    check_joint_separation,
    check_slip,
    check_bolt_shear,
    check_bearing,
    check_surface_pressure,
    check_fatigue,
    check_thread_stripping,
    compute_thread_torque,
    compute_thread_fatigue_limit,
    calculate_all_margins,
)


def _bolt(designation="M12", grade="ISO 8.8"):
    from boltsizer.standards import get_bolt_geometry, get_material
    geom = get_bolt_geometry(designation, shank_length=20.0, threaded_length=15.0)
    mat = get_material(grade, geom.nominal_diameter)
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


def _load_dist(F_ext=10000, V=5000, crit=0, n_bolts=4, F_ext_min=0.0):
    axial_each = F_ext / n_bolts
    return LoadDistributionResult(
        critical_bolt_index=crit,
        F_axial_per_bolt=axial_each,
        F_bend_per_bolt=0.0,
        V_shear_per_bolt=V,
        F_total_axial=F_ext,
        bolt_angles_deg=[0.0, 90.0, 180.0, 270.0][:n_bolts],
        bolt_axial_forces=[F_ext] + [0.0] * (n_bolts - 1),
        V_direct_per_bolt=V,
        V_torsion_per_bolt=0.0,
        F_total_axial_min=F_ext_min,
    )


class TestThreadTorque:
    def test_mu_derivation_sensible(self):
        """M12, K=0.16 → effective μ ≈ 0.12, M_G ≈ 1.0 N·mm per N preload."""
        bolt = _bolt("M12", "ISO 8.8")
        M_G = compute_thread_torque(bolt, 0.16, 1.0)
        assert 0.8 < M_G < 1.2, f"M_G per unit preload = {M_G:.3f} N·mm/N"

    def test_zero_for_frictionless_limit(self):
        """K at the pitch-only limit → μ = 0 → M_G = pitch term only."""
        bolt = _bolt("M12", "ISO 8.8")
        P = bolt.geometry.pitch
        d = bolt.geometry.nominal_diameter
        K_pitch_only = 0.159 * P / d
        M_G = compute_thread_torque(bolt, K_pitch_only, 1000.0)
        assert math.isclose(M_G, 0.159 * P * 1000.0, rel_tol=1e-9)


class TestYieldAssembly:
    def test_pass_when_well_below_yield(self):
        bolt = _bolt("M12", "ISO 8.8")
        pre = _preload(F_M_max=30000)
        ms = check_yield_assembly(bolt, pre, nut_factor_K=0.16)
        assert ms.value > 0, f"Expected positive MS, got {ms.value:.3f}"

    def test_fail_when_over_allowable(self):
        bolt = _bolt("M12", "ISO 8.8")
        A_s = bolt.geometry.stress_area
        sigma_y = bolt.material.yield_strength
        # Axial force alone at 95% of yield → over 0.9·σ_y even without torsion
        pre = _preload(F_M_max=0.95 * A_s * sigma_y)
        ms = check_yield_assembly(bolt, pre, nut_factor_K=None)
        assert ms.value < 0

    def test_torsion_reduces_margin(self):
        """Including the tightening torsion must lower the assembly margin."""
        bolt = _bolt("M12", "ISO 8.8")
        pre = _preload(F_M_max=30000)
        ms_no_torsion = check_yield_assembly(bolt, pre, nut_factor_K=None)
        ms_with_torsion = check_yield_assembly(bolt, pre, nut_factor_K=0.16)
        assert ms_with_torsion.value < ms_no_torsion.value

    def test_ms_formula_axial_only(self):
        """Without torsion: MS = 0.9·σ_y / (F/A_s) − 1."""
        bolt = _bolt("M12", "ISO 8.8")
        A_s = bolt.geometry.stress_area
        sigma_y = bolt.material.yield_strength
        F_M_max = 30000
        pre = _preload(F_M_max=F_M_max)
        ms = check_yield_assembly(bolt, pre, nut_factor_K=None)
        expected = 0.9 * sigma_y / (F_M_max / A_s) - 1
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

    def test_both_standards_use_after_loss_preload(self):
        """Separation allowable must include the embedding loss under BOTH
        conventions — using F_M_min (before losses) would overstate the
        margin (non-conservative)."""
        pre = _preload(F_M_max=40000, F_Z=5000)  # Large embedding
        stiff = _stiffness()
        ms_vdi = check_joint_separation(pre, stiff, F_ext=10000, standard="VDI")
        ms_ecss = check_joint_separation(pre, stiff, F_ext=10000, standard="ECSS")
        assert math.isclose(ms_vdi.allowable, pre.F_preload_min, rel_tol=1e-9)
        assert math.isclose(ms_ecss.allowable, pre.F_preload_min, rel_tol=1e-9)

    def test_separation_fos_reduces_margin(self):
        pre = _preload()
        stiff = _stiffness()
        ms_1 = check_joint_separation(pre, stiff, F_ext=10000, fos_separation=1.0)
        ms_12 = check_joint_separation(pre, stiff, F_ext=10000, fos_separation=1.2)
        assert ms_12.value < ms_1.value
        assert math.isclose(ms_12.value + 1, (ms_1.value + 1) / 1.2, rel_tol=1e-9)


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
        for ms in check_bolt_shear(bolt, V_shear=0.0):
            assert ms.value == float("inf") or ms.value > 100

    def test_shear_capacity_formula(self):
        """Yield shear capacity = 0.577·σ_y·A_d3 (threads in shear plane)."""
        bolt = _bolt("M12", "ISO 8.8")
        A_d3 = bolt.geometry.minor_area
        sigma_y = bolt.material.yield_strength
        sigma_u = bolt.material.uts
        V = 5000
        ms_y, ms_u = check_bolt_shear(bolt, V, shear_plane_in_threads=True)
        assert math.isclose(ms_y.value, 0.577 * A_d3 * sigma_y / V - 1, rel_tol=1e-6)
        assert math.isclose(ms_u.value, 0.577 * A_d3 * sigma_u / V - 1, rel_tol=1e-6)

    def test_shank_plane_uses_nominal_area(self):
        bolt = _bolt("M12", "ISO 8.8")
        ms_thread, _ = check_bolt_shear(bolt, 5000, shear_plane_in_threads=True)
        ms_shank, _ = check_bolt_shear(bolt, 5000, shear_plane_in_threads=False)
        assert ms_shank.value > ms_thread.value


class TestSurfacePressure:
    def test_default_limit_from_plate_yield(self):
        bolt = _bolt("M12", "ISO 8.8")
        pre = _preload(F_M_max=40000)
        stiff = _stiffness()
        ms = check_surface_pressure(bolt, pre, stiff, F_ext=0.0,
                                    surface_pressure_limit=None,
                                    plate_yield_strength=240.0)
        assert math.isclose(ms.allowable, 1.4 * 240.0, rel_tol=1e-9)
        A_p = bolt.geometry.head_bearing_area
        assert math.isclose(ms.applied, 40000 / A_p, rel_tol=1e-9)

    def test_soft_flange_fails(self):
        """High preload on a soft (aluminium-like) flange must fail."""
        bolt = _bolt("M12", "ISO 12.9")
        A_p = bolt.geometry.head_bearing_area
        # Preload chosen so pressure = 3× the 1.4·σ_y limit
        pre = _preload(F_M_max=3 * 1.4 * 120.0 * A_p)
        stiff = _stiffness()
        ms = check_surface_pressure(bolt, pre, stiff, 0.0, None, 120.0)
        assert ms.value < 0


class TestFatigue:
    def test_vdi_limit_when_no_override(self):
        """fatigue_limit=None → VDI σ_ASV = 0.85·(150/d + 45)."""
        bolt = _bolt("M12", "ISO 8.8")
        assert bolt.material.fatigue_limit is None
        sigma = compute_thread_fatigue_limit(bolt)
        assert math.isclose(sigma, 0.85 * (150.0 / 12.0 + 45.0), rel_tol=1e-9)

    def test_grade_independence_of_vdi_limit(self):
        """VDI thread endurance is essentially grade-independent."""
        s88 = compute_thread_fatigue_limit(_bolt("M12", "ISO 8.8"))
        s129 = compute_thread_fatigue_limit(_bolt("M12", "ISO 12.9"))
        assert math.isclose(s88, s129, rel_tol=1e-9)

    def test_rolled_after_ht_increases_limit(self):
        bolt_before = _bolt("M12", "ISO 8.8")
        bolt_after = _bolt("M12", "ISO 8.8")
        bolt_after.thread_rolled = "after_ht"
        F_Sm = 20000.0  # well below F_0.2min
        s_before = compute_thread_fatigue_limit(bolt_before, F_Sm)
        s_after = compute_thread_fatigue_limit(bolt_after, F_Sm)
        assert s_after > s_before

    def test_user_override_used(self):
        geom = _bolt().geometry
        mat = BoltMaterial(name="Test", yield_strength=800, uts=1000,
                           youngs_modulus=210000, fatigue_limit=77.0)
        bolt = Bolt(geometry=geom, material=mat, grade="Test")
        assert math.isclose(compute_thread_fatigue_limit(bolt), 77.0, rel_tol=1e-9)

    def test_fatigue_amplitude_formula(self):
        """σ_a = φ_n·(F_max − F_min)/(2·A_s); MS = σ_AS/σ_a − 1."""
        bolt = _bolt("M12", "ISO 8.8")
        pre = _preload()
        stiff = _stiffness(phi_basic=0.1, n=0.5)
        F_max, F_min = 10000, 2000
        ms = check_fatigue(bolt, pre, stiff, F_ext_max=F_max, F_ext_min=F_min)
        F_SA = stiff.phi_n * (F_max - F_min) / 2
        sigma_a = F_SA / bolt.geometry.stress_area
        sigma_allow = compute_thread_fatigue_limit(bolt, pre.F_M_max + stiff.phi_n * (F_max + F_min) / 2)
        assert math.isclose(ms.value, sigma_allow / sigma_a - 1, rel_tol=1e-6)

    def test_fully_reversed_doubles_amplitude(self):
        """F_min = −F_max must give twice the pulsating amplitude."""
        bolt = _bolt("M12", "ISO 8.8")
        pre = _preload()
        stiff = _stiffness()
        ms_pulsating = check_fatigue(bolt, pre, stiff, 10000, 0.0)
        ms_reversed = check_fatigue(bolt, pre, stiff, 10000, -10000)
        assert math.isclose(ms_reversed.applied, 2 * ms_pulsating.applied, rel_tol=1e-9)


class TestThreadStripping:
    def test_weak_internal_thread_governs(self):
        bolt = _bolt("M12", "ISO 12.9")
        # Aluminium tapped hole (UTS 300) vs high-strength bolt
        ms = check_thread_stripping(bolt, F_bolt_max=30000,
                                    engagement_length=12.0,
                                    internal_thread_uts=300.0)
        assert "internal" in ms.explanation

    def test_longer_engagement_higher_margin(self):
        bolt = _bolt("M12", "ISO 8.8")
        ms_short = check_thread_stripping(bolt, 30000, 8.0, 300.0)
        ms_long = check_thread_stripping(bolt, 30000, 20.0, 300.0)
        assert ms_long.value > ms_short.value


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
        assert len(margins) >= 9

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

    def test_stripping_only_for_tapped(self):
        bolt = _bolt("M12", "ISO 8.8")
        pre = _preload()
        stiff = _stiffness()
        ld = _load_dist()
        iface = self._make_interface()
        lc = ExternalLoading(axial_force=10000, bending_moment=0, shear_force=5000)
        margins_nut = calculate_all_margins(bolt, pre, stiff, ld, iface, lc)
        assert not any(m.check_name == "Thread Stripping" for m in margins_nut)
        margins_tapped = calculate_all_margins(
            bolt, pre, stiff, ld, iface, lc,
            tapped_engagement_length=12.0, tapped_material_uts=300.0,
        )
        assert any(m.check_name == "Thread Stripping" for m in margins_tapped)

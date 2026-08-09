"""Reference validation tests.

Unlike the module unit tests, these verify the implementation against
INDEPENDENT references: hand-derived closed-form values, standard-formula
recomputation of data tables, dimensional/physical sanity bands, and
end-to-end orchestrator behaviour.  These tests are designed to catch the
class of defect found in the 2026-08 calculation audit (dimensional
errors, inverted conventions, non-conservative data).
"""
import math
import pytest
from boltsizer.models.bolt import Bolt
from boltsizer.models.joint import BoltCircle, ClampedLayer, ClampedInterface, ExternalLoading
from boltsizer.standards import get_bolt_geometry, get_material
from boltsizer.standards.bolt_library import BOLT_LIBRARY
from boltsizer.calculations.joint_stiffness import calculate_joint_stiffness
from boltsizer.calculations.preload import calculate_preload
from boltsizer.calculations.load_distribution import calculate_load_distribution
from boltsizer.calculations.vdi2230 import run_vdi2230_analysis


def _m12_circle(**kw):
    geom = get_bolt_geometry("M12", shank_length=20.0, threaded_length=15.0)
    mat = get_material("ISO 8.8", 12.0)
    bolt = Bolt(geometry=geom, material=mat, grade="ISO 8.8")
    defaults = dict(
        num_bolts=8, bolt_circle_diameter=100.0, bolt=bolt,
        nut_factor_K=0.16, assembly_torque=85000,
    )
    defaults.update(kw)
    return BoltCircle(**defaults)


def _steel_iface(t=20.0, n=2, **kw):
    return ClampedInterface(
        total_clamped_length=0.0,
        layers=[ClampedLayer("Steel (carbon)", t, 210000) for _ in range(n)],
        interface_treatment="bare metal",
        friction_coefficient=0.12,
        **kw,
    )


class TestStiffnessReference:
    """δ_S and δ_P against hand-evaluated closed forms (M12, 2×20mm steel)."""

    def test_delta_S_matches_vdi_hand_calc(self):
        bc = _m12_circle()
        r = calculate_joint_stiffness(bc, _steel_iface())
        # Hand: 0.4d/(EA_N) + 20/(EA_N) + 20/(EA_d3) + 0.5d/(EA_d3) + 0.4d/(EA_N)
        geom = bc.bolt.geometry
        E = 210000.0
        A_N, A_d3, d = geom.nominal_area, geom.minor_area, 12.0
        expected = (0.4*d + 20.0 + 0.4*d)/(E*A_N) + (20.0 + 0.5*d)/(E*A_d3)
        assert math.isclose(r.delta_S, expected, rel_tol=1e-9)

    def test_delta_P_matches_frustum_hand_calc(self):
        """δ_P must equal two opposed 20 mm frusta (closed form incl. d_h)."""
        bc = _m12_circle()
        r = calculate_joint_stiffness(bc, _steel_iface())
        geom = bc.bolt.geometry
        E, tanp = 210000.0, math.tan(math.radians(30.0))
        dw, dh = geom.head_bearing_diameter, geom.hole_diameter
        D2 = dw + 2 * 20.0 * tanp
        expected = 2 * math.log(((D2 - dh) * (dw + dh)) / ((D2 + dh) * (dw - dh))) \
            / (math.pi * E * dh * tanp)
        assert math.isclose(r.delta_P, expected, rel_tol=1e-9)

    def test_delta_P_dimensional_band(self):
        """Regression guard for the audited d_h dimensional error: a steel
        M12 joint must land in the physically plausible compliance band."""
        r = calculate_joint_stiffness(_m12_circle(), _steel_iface())
        assert 2e-7 < r.delta_P < 1.5e-6, f"delta_P = {r.delta_P:.3e} mm/N"

    def test_phi_band_steel_joint(self):
        """Steel-on-steel joints must have φ ≈ 0.1–0.35 (audited bug gave 0.67)."""
        r = calculate_joint_stiffness(_m12_circle(), _steel_iface())
        assert 0.10 < r.phi_basic < 0.35, f"phi = {r.phi_basic:.3f}"

    def test_layer_split_invariance(self):
        """One 40 mm layer ≡ two 20 mm layers of the same material."""
        bc = _m12_circle()
        r1 = calculate_joint_stiffness(bc, _steel_iface(t=40.0, n=1))
        r2 = calculate_joint_stiffness(bc, _steel_iface(t=20.0, n=2))
        assert math.isclose(r1.delta_P, r2.delta_P, rel_tol=1e-9)

    def test_available_diameter_cap_increases_compliance(self):
        bc = _m12_circle()
        r_wide = calculate_joint_stiffness(bc, _steel_iface())
        r_narrow = calculate_joint_stiffness(bc, _steel_iface(available_diameter=20.0))
        assert r_narrow.delta_P > r_wide.delta_P


class TestPreloadReference:
    def test_symmetric_scatter(self):
        """F_M_max/min = F_nom·(1±ε) with ε = (α−1)/(α+1); ratio = α."""
        bc = _m12_circle()
        r = calculate_preload(bc, 40.0, total_compliance=3.5e-6)
        alpha = r.alpha_A
        eps = (alpha - 1) / (alpha + 1)
        assert math.isclose(r.F_M_max, r.F_M_nominal * (1 + eps), rel_tol=1e-9)
        assert math.isclose(r.F_M_min, r.F_M_nominal * (1 - eps), rel_tol=1e-9)
        assert math.isclose(r.F_M_max / r.F_M_min, alpha, rel_tol=1e-9)

    def test_embedding_uses_joint_compliance(self):
        """F_Z = f_Z / (δ_S + δ_P) exactly."""
        bc = _m12_circle()
        total_c = 3.4755e-6
        r = calculate_preload(bc, 40.0, total_compliance=total_c,
                              num_inner_interfaces=1)
        assert math.isclose(r.F_Z, r.f_Z_displacement / total_c, rel_tol=1e-9)

    def test_embedding_guide_values_axial_rz6(self):
        """Rz = 6.3 μm, 1 inner interface, axial: f_Z = 3 + 2·2.5 + 1.5 = 9.5 μm."""
        bc = _m12_circle(surface_roughness_Rz=6.3)
        r = calculate_preload(bc, 40.0, total_compliance=3.5e-6,
                              num_inner_interfaces=1)
        assert math.isclose(r.f_Z_displacement, 9.5e-3, rel_tol=1e-9)

    def test_k_range_envelope_widens_bounds(self):
        bc_plain = _m12_circle()
        bc_range = _m12_circle(nut_factor_K_min=0.10, nut_factor_K_max=0.25)
        r_plain = calculate_preload(bc_plain, 40.0, total_compliance=3.5e-6)
        r_range = calculate_preload(bc_range, 40.0, total_compliance=3.5e-6)
        # K_min = 0.10 → F = M/(K_min·d) far above the α_A band
        assert r_range.F_M_max > r_plain.F_M_max
        assert r_range.F_M_min < r_plain.F_M_min
        assert math.isclose(r_range.F_M_max, 85000 / (0.10 * 12), rel_tol=1e-9)
        assert math.isclose(r_range.F_M_min, 85000 / (0.25 * 12), rel_tol=1e-9)


class TestLoadDistributionReference:
    def test_bending_closed_form_max(self):
        """Max bending bolt force = 2M/(n·r) = 4M/(n·D) for n ≥ 3."""
        bc = _m12_circle(num_bolts=8, bolt_circle_diameter=100.0)
        M = 500000.0
        lc = ExternalLoading(axial_force=0, bending_moment=M, shear_force=0)
        r = calculate_load_distribution(bc, lc)
        assert math.isclose(r.F_total_axial, 2 * M / (8 * 50.0), rel_tol=1e-9)

    def test_torsion_adds_tangential_shear(self):
        """V_t = M_T/(n_B·r) must appear in the per-bolt shear."""
        bc = _m12_circle(num_bolts=8, bolt_circle_diameter=100.0)
        lc = ExternalLoading(axial_force=0, bending_moment=0,
                             shear_force=8000, torsion=400000)
        r = calculate_load_distribution(bc, lc)
        assert math.isclose(r.V_torsion_per_bolt, 400000 / (8 * 50.0), rel_tol=1e-9)
        assert math.isclose(r.V_shear_per_bolt, 8000 / 8 + 1000.0, rel_tol=1e-9)

    def test_min_load_set_on_same_bolt(self):
        bc = _m12_circle(num_bolts=8, bolt_circle_diameter=100.0)
        lc = ExternalLoading(axial_force=16000, bending_moment=200000,
                             shear_force=0, axial_force_min=8000,
                             bending_moment_min=100000)
        r = calculate_load_distribution(bc, lc)
        # Min set is exactly half the max set → same distribution, halved
        assert math.isclose(r.F_total_axial_min, r.F_total_axial / 2, rel_tol=1e-9)


class TestBoltLibrarySelfConsistency:
    """Recompute every table entry from the standard formulas."""

    def test_iso_stress_areas(self):
        for desig, e in BOLT_LIBRARY.items():
            if not e["standard"].startswith("ISO"):
                continue
            d, p = e["nominal_diameter"], e["pitch"]
            d2, d3 = d - 0.6495 * p, d - 1.2269 * p
            A_s = math.pi / 4 * ((d2 + d3) / 2) ** 2
            assert abs(e["stress_area"] - A_s) / A_s < 0.01, (
                f"{desig}: table A_s={e['stress_area']} vs formula {A_s:.2f}")
            assert abs(e["pitch_diameter"] - d2) < 0.01, desig
            assert abs(e["minor_diameter"] - d3) < 0.01, desig

    def test_unified_stress_areas(self):
        for desig, e in BOLT_LIBRARY.items():
            if e["standard"] != "Unified":
                continue
            d_mm, p_mm = e["nominal_diameter"], e["pitch"]
            d_in, n_tpi = d_mm / 25.4, 25.4 / p_mm
            A_s = 0.7854 * (d_in - 0.9743 / n_tpi) ** 2 * 645.16
            assert abs(e["stress_area"] - A_s) / A_s < 0.01, (
                f"{desig}: table A_s={e['stress_area']} vs formula {A_s:.2f}")

    def test_bearing_geometry_sane(self):
        for desig, e in BOLT_LIBRARY.items():
            assert e["head_bearing_diameter"] > e["hole_diameter"] > e["nominal_diameter"], desig
            A_p = math.pi / 4 * (e["head_bearing_diameter"] ** 2 - e["hole_diameter"] ** 2)
            assert math.isclose(e["head_bearing_area"], A_p, rel_tol=1e-6), desig


class TestMaterialLibraryReference:
    def test_iso_898_1_minimums(self):
        m88_small = get_material("ISO 8.8", 12.0)
        assert m88_small.yield_strength == 640
        assert m88_small.proof_load_stress == 580
        m88_large = get_material("ISO 8.8", 20.0)
        assert m88_large.yield_strength == 660
        assert m88_large.proof_load_stress == 600
        assert get_material("ISO 10.9", 12.0).yield_strength == 940
        assert get_material("ISO 12.9", 12.0).yield_strength == 1100

    def test_no_smooth_bar_fatigue_limits(self):
        """Library materials must not carry smooth-bar fatigue limits."""
        for grade in ("ISO 8.8", "ISO 10.9", "ISO 12.9", "A286", "Inconel 718"):
            assert get_material(grade, 10.0).fatigue_limit is None, grade


class TestEndToEnd:
    """Orchestrator-level behaviour on the M12 reference joint."""

    def _run(self, **kw):
        bc = _m12_circle()
        iface = _steel_iface()
        lc_kw = dict(axial_force=10000, bending_moment=0, shear_force=5000)
        lc_kw.update(kw.pop("lc_kw", {}))
        lcs = [ExternalLoading(**lc_kw)]
        return run_vdi2230_analysis(bc, iface, lcs, **kw)

    def test_smoke_and_phi_band(self):
        res = self._run()
        case = res.case_results[0]
        assert 0.10 < case.stiffness.phi_basic < 0.35
        assert len(case.margins) >= 9
        assert sum(1 for m in case.margins if m.binding) == 1

    def test_thermal_loss_reduces_min_preload(self):
        """Steel bolt in aluminium flanges, hot case → preload loss...
        (Al expands MORE than steel → clamp grows → preload RISES; the
        cold case loses preload).  Verify both directions."""
        bc = _m12_circle()
        iface = ClampedInterface(
            total_clamped_length=0.0,
            layers=[ClampedLayer("Aluminium alloy", 20.0, 70000),
                    ClampedLayer("Aluminium alloy", 20.0, 70000)],
            interface_treatment="bare metal",
            friction_coefficient=0.12,
        )
        lcs = [
            ExternalLoading(axial_force=10000, bending_moment=0, shear_force=0,
                            delta_T=0.0, case_name="ambient"),
            ExternalLoading(axial_force=10000, bending_moment=0, shear_force=0,
                            delta_T=-60.0, case_name="cold"),
            ExternalLoading(axial_force=10000, bending_moment=0, shear_force=0,
                            delta_T=+60.0, case_name="hot"),
        ]
        res = run_vdi2230_analysis(bc, iface, lcs)
        ambient, cold, hot = res.case_results
        # Cold: aluminium shrinks more than the steel bolt → preload loss
        assert cold.F_thermal_delta > 0
        assert cold.preload.F_preload_min < ambient.preload.F_preload_min
        # Hot: aluminium grows more → preload gain applied to the max bound
        assert hot.F_thermal_delta < 0
        assert hot.preload.F_preload_max > ambient.preload.F_preload_max

    def test_ecss_fos_defaults_lower_margins(self):
        res_vdi = self._run(standard="VDI")
        res_ecss = self._run(standard="ECSS")
        def margin(res, name):
            return next(m for m in res.case_results[0].margins if m.check_name == name)
        assert margin(res_ecss, "Yield (Working Load)").value < \
            margin(res_vdi, "Yield (Working Load)").value
        assert margin(res_ecss, "Joint Separation").value < \
            margin(res_vdi, "Joint Separation").value

    def test_load_plane_bolt_head_uses_n_1(self):
        res = self._run(lc_kw={"load_plane": "bolt_head"})
        case = res.case_results[0]
        assert case.stiffness.load_intro_factor_n == 1.0
        assert math.isclose(case.stiffness.phi_n, case.stiffness.phi_basic, rel_tol=1e-9)

    def test_assembly_yield_includes_torsion(self):
        """Torque-mode analyses must carry tightening torsion in the
        assembly yield check (τ term in the explanation ≠ 0)."""
        res = self._run()
        asm = next(m for m in res.case_results[0].margins
                   if m.check_name == "Yield at Assembly")
        assert "τ_M = 0.0" not in asm.explanation

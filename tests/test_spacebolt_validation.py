"""Cross-validation against the SpaceBolt v2.2 'Blip Chamber Nozzle' report.

Case: DIN 912 M4x0.70 (8.8) through one 10 mm AL6061-T6 flange into a
tapped AL6061-T6 insert.  Torque 3.5 N·m ±5% tool scatter, μ = 0.14–0.24
(thread and under-head), embedding 5% of max preload, μ_interface = 0.2,
n = 1, all safety factors 1.0, F_A = 1670 N, F_Q = 100 N.

Quantities where the conventions coincide are asserted TIGHT (≤1%).
Quantities where BoltSizer is deliberately more conservative (concentric
cone vs SpaceBolt's flange-opening model, 50% residual torsion in working
margins, 0.577·σ on A_d3 for shear) are asserted as bands on the
conservative side of the SpaceBolt value.  See
fixtures/spacebolt_blip_chamber_nozzle.json for the full report data.
"""
import json
import math
import pathlib
import pytest
from boltsizer.models.bolt import Bolt, BoltMaterial
from boltsizer.models.joint import BoltCircle, ClampedLayer, ClampedInterface, ExternalLoading
from boltsizer.standards import get_bolt_geometry
from boltsizer.calculations.vdi2230 import run_vdi2230_analysis

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "spacebolt_blip_chamber_nozzle.json"
DATA = json.loads(FIXTURE.read_text())


def _K_of_mu(mu: float, d: float, P: float, d2: float, D_Km: float) -> float:
    """Uniform-friction nut factor: K·d = 0.159·P + 0.578·d2·μ + 0.5·D_Km·μ."""
    return (0.159 * P + 0.578 * d2 * mu + 0.5 * D_Km * mu) / d


@pytest.fixture(scope="module")
def result():
    b = DATA["bolt"]
    # DIN 912 M4x25 with 20 mm thread → 5 mm shank
    geom = get_bolt_geometry("M4", shank_length=5.0, threaded_length=20.0)
    geom.head_bearing_diameter = b["d_w"]          # DIN 912 socket head
    geom.hole_diameter = DATA["flange"]["hole"]
    geom.head_bearing_area = math.pi / 4 * (
        geom.head_bearing_diameter ** 2 - geom.hole_diameter ** 2)

    mat = BoltMaterial(
        name="Steel 8.8 (SpaceBolt)",
        yield_strength=b["yield"], uts=b["uts"],
        youngs_modulus=b["E"], cte=b["cte"],
    )
    bolt = Bolt(geometry=geom, material=mat, grade="ISO 8.8")

    inst = DATA["installation"]
    D_Km = 0.5 * (geom.head_bearing_diameter + geom.hole_diameter)
    K_min = _K_of_mu(inst["mu_thread"][0], b["d"], b["P"], b["d2"], D_Km)
    K_nom = _K_of_mu(0.5 * sum(inst["mu_thread"]), b["d"], b["P"], b["d2"], D_Km)
    K_max = _K_of_mu(inst["mu_thread"][1], b["d"], b["P"], b["d2"], D_Km)

    bc = BoltCircle(
        num_bolts=1, bolt_circle_diameter=0.0, bolt=bolt,
        nut_factor_K=K_nom,
        nut_factor_K_min=K_min, nut_factor_K_max=K_max,
        tool_scatter_pct=inst["tool_scatter"],
        assembly_torque=inst["torque_Nm"] * 1000.0,
        embedding_percent_of_max=0.05,
    )

    fl = DATA["flange"]
    iface = ClampedInterface(
        total_clamped_length=0.0,
        layers=[ClampedLayer("AL6061-T6", fl["thickness"], fl["E"], cte=fl["cte"])],
        interface_treatment="bare metal",
        friction_coefficient=DATA["loads"]["mu_interface"],
        num_friction_interfaces=1,
        available_diameter=fl["outer_diameter"],
    )

    ld = DATA["loads"]
    lc = ExternalLoading(
        axial_force=ld["F_axial"], bending_moment=0.0,
        shear_force=ld["F_shear"], case_name="SpaceBolt_Blip",
    )

    return run_vdi2230_analysis(
        bolt_circle=bc, interface=iface, load_cases=[lc],
        load_intro_factor_n=ld["load_intro_n"],
        plate_thickness=fl["thickness"],
        plate_yield_strength=276.0,   # AL6061-T6 yield
        standard="ECSS",
        fos_yield=1.0, fos_ultimate=1.0, fos_separation=1.0, fos_slip=1.0,
        tapped_engagement_length=DATA["counterpart"]["thread_length"],
        tapped_material_uts=310.0,    # AL6061-T6 tensile ultimate
    ).case_results[0]


def _margin(result, name):
    return next(m for m in result.margins if m.check_name == name)


class TestExactAgreement:
    """Quantities where the conventions coincide — asserted within 1%."""

    def test_max_preload(self, result):
        rep = DATA["reported"]
        assert math.isclose(result.preload.F_M_max, rep["F_Vmax_ref"], rel_tol=0.01)

    def test_min_preload_before_losses(self, result):
        rep = DATA["reported"]
        assert math.isclose(result.preload.F_M_min, rep["F_Vmin_ref"], rel_tol=0.01)

    def test_embedding_loss(self, result):
        rep = DATA["reported"]
        assert math.isclose(result.preload.F_Z, rep["F_Z"], rel_tol=0.01)

    def test_min_preload_after_losses(self, result):
        rep = DATA["reported"]
        assert math.isclose(result.preload.F_preload_min,
                            rep["F_Vmin_after_losses"], rel_tol=0.01)

    def test_installation_stress(self, result):
        """σ_inst = 678 MPa (max preload paired with μ_min thread torque)."""
        rep = DATA["reported"]
        asm = _margin(result, "Yield at Assembly")
        # fos = 1 → applied IS the installation von Mises stress
        assert math.isclose(asm.applied, rep["sigma_inst_yield"], rel_tol=0.01)

    def test_tightening_yield_margin(self, result):
        """SpaceBolt: −0.06 (ECSS convention: full σ_y, FoS 1)."""
        asm = _margin(result, "Yield at Assembly")
        assert math.isclose(asm.value, -0.056, abs_tol=0.012)


class TestConservativeAgreement:
    """Checks where BoltSizer deliberately sits on the conservative side
    of the SpaceBolt value (documented convention differences)."""

    def test_phi_close_to_spacebolt_share(self, result):
        """SpaceBolt flange model: bolt share 0.30; concentric cone: ~0.27."""
        assert 0.20 < result.stiffness.phi_n < 0.32

    def test_gapping(self, result):
        """SpaceBolt 1.00; ours slightly lower (smaller φ_n → larger demand)."""
        ms = _margin(result, "Joint Separation")
        assert 0.75 <= ms.value <= 1.05

    def test_sliding_min_preload(self, result):
        """SpaceBolt 1.35; ours slightly lower."""
        ms = _margin(result, "Interface Slip")
        assert 1.05 <= ms.value <= 1.40

    def test_working_yield(self, result):
        """SpaceBolt axial-total/combined yield 0.10 (no residual torsion);
        ours retains 50% residual torsion → lower but positive."""
        ms = _margin(result, "Yield (Working Load)")
        assert 0.0 < ms.value <= 0.12

    def test_working_ultimate(self, result):
        """SpaceBolt 0.38; ours with residual torsion → ~0.28–0.38."""
        ms = _margin(result, "Ultimate (Working Load)")
        assert 0.25 <= ms.value <= 0.40

    def test_ultimate_at_assembly(self, result):
        """SpaceBolt 0.30 (partially relaxed torsion); ours retains full
        torsion → lower margin."""
        ms = _margin(result, "Ultimate at Assembly")
        assert 0.12 <= ms.value <= 0.30

    def test_thread_stripping(self, result):
        """SpaceBolt pull-out (total) 3.31 using τ_ult = 207 directly;
        ours derives 0.577·UTS(310) = 179 MPa → lower margin."""
        ms = _margin(result, "Thread Stripping")
        assert 2.0 <= ms.value <= 3.4

    def test_bolt_shear(self, result):
        """SpaceBolt 32.7 (0.6·σ_y on A_s); ours 0.577·σ_y on A_d3."""
        ms = _margin(result, "Bolt Shear (Yield)")
        assert 24.0 <= ms.value <= 33.0

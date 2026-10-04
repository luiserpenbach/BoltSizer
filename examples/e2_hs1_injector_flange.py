"""E2-HS-1 thrust chamber — injector flange joint (14 × M6 into 6082-T6).

Worked example of a BoltSizer run for the Hopper E2 heat sink chamber
(design description "Thrust Chamber E2-HS-1", Draft 2, 2026-09-26, and
E2-REG-1 §9.3 for the shared injector interface).

Joint (from the design documents):
  - 14 × M6 ISO 4762 socket head cap screws on PCD 122 mm, A2-80 (TBC;
    E2-REG-1 uses A4-80, identical strength class)
  - clamped: Nord-Lock washer pair 2 mm (TBC) + injector head flange
    10 mm 316L (TBC)
  - tapped directly into the EN AW-6082 T6 chamber cylinder, no inserts (SN1)
  - pressure load inside the 110 mm seal diameter (TBC):
      MEOP 25 bar → 23.8 kN total, 1.70 kN per screw
  - factors (handbook 11.5, proposed): yield 1.25 / ultimate 2.0 at MEOP,
    proof 1.5 × MEOP, hard start 2 × MEOP with 1.0 on ultimate

Assumptions made here because the documents leave them TBD — every one is
a named constant below so it can be updated when the drawings close:
  - thread engagement in the aluminium: 12 mm (2·d)
  - friction μ = 0.14–0.24 (thread and under head), torque tool ±5 %,
    embedding 5 % of max preload (the team's SpaceBolts conventions, as in
    the Blip Chamber Nozzle report)
  - 6082-T6 R_m = 290 MPa (lower end of the 290–310 MPa range in §8)
  - 316L flange R_p0.2 = 200 MPa for the head surface-pressure check
  - available cone diameter D_A = 18 mm (2 × 9 mm edge distance to the
    140 mm chamber OD; injector flange OD not documented)
  - load introduction factor n = 0.5; soak-back ΔT = +60 K (§7.2)

Run:  python examples/e2_hs1_injector_flange.py
"""
from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from boltsizer.models.bolt import Bolt, BoltMaterial
from boltsizer.models.joint import BoltCircle, ClampedInterface, ClampedLayer, ExternalLoading
from boltsizer.standards import get_bolt_geometry
from boltsizer.calculations.vdi2230 import run_vdi2230_analysis
from boltsizer.calculations.sizing import torque_window
from boltsizer.calculations.joint_stiffness import _frustum_slice_compliance

# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
N_BOLTS = 14
PCD = 122.0                  # [mm]
SEAL_D = 110.0               # [mm] pressure diameter (TBC)
MEOP_BAR = 25.0
DELTA_T_SOAK = 60.0          # [K] bulk soak-back after a 2 s burn (§7.2)

L_ENGAGE = 12.0              # [mm] ASSUMED thread engagement in 6082-T6
ALU_UTS = 290.0              # [MPa] 6082-T6, lower end of range
FLANGE_YIELD_316L = 200.0    # [MPa] for head surface pressure
D_A = 18.0                   # [mm] ASSUMED available cone diameter
N_INTRO = 0.5                # load introduction factor
MU_RANGE = (0.14, 0.24)      # thread and under-head friction
TOOL_SCATTER = 0.05

D_W_ISO4762 = 9.38           # [mm] ISO 4762 M6 d_w,min
D_H = 6.6                    # [mm] ISO 273 medium clearance hole


def pressure_load(p_bar: float) -> float:
    """Total separating force [N] from pressure inside the seal diameter."""
    return p_bar * 0.1 * math.pi / 4.0 * SEAL_D ** 2


def nut_factor(mu: float, d: float, P: float, d2: float, D_Km: float) -> float:
    """Uniform-friction nut factor: K·d = 0.159·P + 0.578·d2·μ + 0.5·D_Km·μ."""
    return (0.159 * P + 0.578 * d2 * mu + 0.5 * D_Km * mu) / d


def build_joint(torque_Nmm: float):
    geom = get_bolt_geometry("M6", shank_length=0.0, threaded_length=24.0)
    geom.head_bearing_diameter = D_W_ISO4762
    geom.hole_diameter = D_H
    geom.head_bearing_area = math.pi / 4 * (D_W_ISO4762 ** 2 - D_H ** 2)

    mat = BoltMaterial(
        name="A2-80", yield_strength=600.0, uts=800.0,
        youngs_modulus=193000.0, proof_load_stress=600.0, cte=16.0e-6,
    )
    bolt = Bolt(geometry=geom, material=mat, grade="A2-80")

    d, P, d2 = geom.nominal_diameter, geom.pitch, geom.pitch_diameter
    D_Km = 0.5 * (D_W_ISO4762 + D_H)
    K_min = nut_factor(MU_RANGE[0], d, P, d2, D_Km)
    K_nom = nut_factor(sum(MU_RANGE) / 2, d, P, d2, D_Km)
    K_max = nut_factor(MU_RANGE[1], d, P, d2, D_Km)

    bc = BoltCircle(
        num_bolts=N_BOLTS, bolt_circle_diameter=PCD, bolt=bolt,
        nut_factor_K=K_nom, nut_factor_K_min=K_min, nut_factor_K_max=K_max,
        tool_scatter_pct=TOOL_SCATTER, assembly_torque=torque_Nmm,
        embedding_percent_of_max=0.05,
    )
    iface = ClampedInterface(
        total_clamped_length=0.0,
        layers=[
            ClampedLayer("Nord-Lock washer (steel)", 2.0, 210000.0, cte=11.5e-6),
            ClampedLayer("Injector flange 316L", 10.0, 193000.0, cte=16.0e-6),
        ],
        interface_treatment="bare metal",
        friction_coefficient=0.2,
        num_friction_interfaces=1,
        available_diameter=D_A,
    )
    return bc, iface


def cases(p_bar: float, name: str, dT: float = 0.0):
    F = pressure_load(p_bar)
    return ExternalLoading(axial_force=F, bending_moment=0.0, shear_force=0.0,
                           axial_force_min=0.0, delta_T=dT, case_name=name)


COMMON = dict(
    load_intro_factor_n=N_INTRO,
    plate_thickness=10.0,
    plate_yield_strength=FLANGE_YIELD_316L,
    standard="ECSS",
    tapped_engagement_length=L_ENGAGE,
    tapped_material_uts=ALU_UTS,
)
GROUPS = {
    # name: (load cases, FoS overrides, pass criterion)
    "Operation (MEOP 25 bar)": (
        [cases(MEOP_BAR, "MEOP cold"), cases(MEOP_BAR, "MEOP hot +60K", DELTA_T_SOAK)],
        dict(fos_yield=1.25, fos_ultimate=2.0, fos_separation=1.2, fos_slip=1.0),
        "all margins",
    ),
    "Proof (1.5 x MEOP = 37.5 bar)": (
        [cases(1.5 * MEOP_BAR, "Proof")],
        dict(fos_yield=1.0, fos_ultimate=1.0, fos_separation=1.0, fos_slip=1.0),
        "no leak (separation), no yield",
    ),
    "Hard start (2 x MEOP = 50 bar)": (
        [cases(2.0 * MEOP_BAR, "Hard start")],
        dict(fos_yield=1.0, fos_ultimate=1.0, fos_separation=1.0, fos_slip=1.0),
        "no rupture (ultimate, stripping)",
    ),
}
SHOW = [
    "Yield at Assembly", "Ultimate at Assembly", "Yield (Working Load)",
    "Ultimate (Working Load)", "Joint Separation", "Thread Stripping",
    "Surface Pressure (Head)", "Fatigue (Infinite Life)",
]


def ecss_external_fos_margins(case, fos_y, fos_u, bolt):
    """Yield/ultimate margins with the FoS on the external load only
    (F_b = F_V,max + φ_n·FOS·F_A) — the ECSS-E-HB-32-23A form — for
    comparison with BoltSizer's FoS-on-total-stress convention."""
    A_s = bolt.geometry.stress_area
    F_A = case.load_dist.F_total_axial
    pre, st = case.preload, case.stiffness
    out = {}
    for label, sig, fos in (("yield", bolt.material.yield_strength, fos_y),
                            ("ultimate", bolt.material.uts, fos_u)):
        F_b = pre.F_preload_max + st.phi_n * fos * F_A
        out[label] = sig * A_s / F_b - 1.0
    return out


def main(torque_Nm: float | None = None) -> None:
    print("E2-HS-1 injector flange — 14 × M6 A2-80 tapped into 6082-T6\n")
    for p in (MEOP_BAR, 1.5 * MEOP_BAR, 2 * MEOP_BAR):
        print(f"  p = {p:5.1f} bar → {pressure_load(p)/1e3:5.2f} kN total, "
              f"{pressure_load(p)/N_BOLTS/1e3:4.2f} kN per screw")

    # --- Torque window over the operating group (sets the spec torque) ---
    bc0, iface = build_joint(8000.0)
    lcs, fos, _ = GROUPS["Operation (MEOP 25 bar)"]
    win = torque_window(bc0, iface, lcs, torque_min=1000.0, torque_max=16000.0,
                        points=61, **COMMON, **fos)
    print("\nTorque window (operation group, all margins ≥ 0):")
    if win["window"]:
        w, r = win["window"], win["recommended"]
        print(f"  {w['t_lo']/1e3:.2f} – {w['t_hi']/1e3:.2f} N·m; best "
              f"{r['torque']/1e3:.2f} N·m (min MS {r['min_ms']:+.2f}, {r['governing']})")
    else:
        print("  NONE — no torque satisfies all operating margins")
    for pt in win["points"][::6]:
        print(f"    {pt['torque']/1e3:5.2f} N·m  min MS {pt['min_ms']:+.2f}  ({pt['governing']})")

    T = (torque_Nm * 1000.0) if torque_Nm else 8000.0
    bc, iface = build_joint(T)
    print(f"\n=== Evaluation at M_A = {T/1e3:.1f} N·m ===")
    for gname, (lcs, fos, crit) in GROUPS.items():
        res = run_vdi2230_analysis(bc, iface, lcs, **COMMON, **fos)
        print(f"\n--- {gname}  [criterion: {crit}] ---")
        for case in res.case_results:
            pre, st = case.preload, case.stiffness
            print(f"  {case.case_name}: F_M = {pre.F_M_min:.0f}–{pre.F_M_max:.0f} N, "
                  f"F_V,min after losses = {pre.F_preload_min:.0f} N, "
                  f"φ = {st.phi_basic:.3f}, φ_n = {st.phi_n:.3f}, "
                  f"F_A/bolt = {case.load_dist.F_total_axial:.0f} N, "
                  f"F_S,max = {case.bolt_load_max:.0f} N, "
                  f"ΔF_th = {case.F_thermal_delta:+.0f} N")
            by = {m.check_name: m for m in case.margins}
            for n in SHOW:
                m = by.get(n)
                if m:
                    print(f"    {n:26s} MS = {m.value:+7.2f}  {m.status}")
            if gname.startswith("Operation"):
                alt = ecss_external_fos_margins(case, fos["fos_yield"], fos["fos_ultimate"], bc.bolt)
                print(f"    (ECSS FoS-on-F_A form: yield {alt['yield']:+.2f}, "
                      f"ultimate {alt['ultimate']:+.2f})")
            for w in case.warnings:
                print(f"    ! {w}")

    # --- Sensitivity: thread engagement in aluminium ---
    print("\nThread stripping vs engagement (hard start, M_A as above):")
    lcs, fos, _ = GROUPS["Hard start (2 x MEOP = 50 bar)"]
    for L in (6.0, 8.0, 9.0, 12.0, 15.0):
        kw = dict(COMMON, tapped_engagement_length=L)
        res = run_vdi2230_analysis(bc, iface, lcs, **kw, **fos)
        m = next(m for m in res.case_results[0].margins if m.check_name == "Thread Stripping")
        print(f"  L_e = {L:4.1f} mm: MS = {m.value:+.2f}  ({m.explanation})")

    # --- Sensitivity: tapped-joint (ESV) stiffness model ---
    # VDI 2230 treats a tapped joint with ONE cone from the head over l_K
    # and the engaged-thread term on the tapped part's modulus.  BoltSizer
    # always uses two opposed cones; compare φ.
    st = run_vdi2230_analysis(bc, iface, GROUPS["Operation (MEOP 25 bar)"][0][:1],
                              **COMMON, **GROUPS["Operation (MEOP 25 bar)"][1]).case_results[0].stiffness
    tanp = math.tan(math.radians(30.0))
    dP_single = (_frustum_slice_compliance(0, 2, 210000.0, D_W_ISO4762, D_H, tanp, D_A)
                 + _frustum_slice_compliance(2, 12, 193000.0, D_W_ISO4762, D_H, tanp, D_A))
    g = bc.bolt.geometry
    dS_esv = st.delta_S - 0.4 * 6 / (193000 * g.nominal_area) + 0.33 * 6 / (70000 * g.nominal_area)
    phi_esv = dP_single / (dS_esv + dP_single)
    print(f"\nStiffness model check: two-cone φ = {st.phi_basic:.3f} "
          f"(δ_S {st.delta_S:.3e}, δ_P {st.delta_P:.3e}); "
          f"tapped-joint single cone + Al thread term φ ≈ {phi_esv:.3f} "
          f"(δ_S {dS_esv:.3e}, δ_P {dP_single:.3e})")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else None)

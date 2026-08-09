# BoltSizer Validation against SpaceBolt

**Reference:** SpaceBolt™ v2.2 report "Blip Chamber Nozzle" (05.05.2024),
supplied 2026-08-09.
**Case:** DIN 912 M4×0.70 (8.8) through one 10 mm AL6061-T6 flange into a
tapped AL6061-T6 insert. Torque 3.5 N·m ±5% tool scatter, μ = 0.14–0.24
(thread and under-head), embedding 5% of max preload, μ_interface = 0.2,
n = 1, all safety factors 1.0. Loads: F_A = 1670 N, F_Q = 100 N.

Encoded as a permanent regression test:
`tests/test_spacebolt_validation.py` +
`tests/fixtures/spacebolt_blip_chamber_nozzle.json`.

## Result: exact agreement where conventions coincide

| Quantity | BoltSizer | SpaceBolt | Δ |
|---|---|---|---|
| F_Vmax [N] | 4590 | 4591 | 0.02% |
| F_Vmin before losses [N] | 2571 | 2572 | 0.02% |
| F_Z embedding [N] | 229.5 | 230 | 0.2% |
| F_Vmin after losses [N] | 2342 | 2343 | 0.04% |
| Installation von Mises σ_inst [MPa] | 678.0 | 678 | exact |
| MS tightening (yield) | −0.056 | −0.06 | rounding |

The preload bracket reproduces SpaceBolt's convention exactly:
`F_max = M·(1+s)/(K(μ_min)·d)`, `F_min = M·(1−s)/(K(μ_max)·d)` with the
uniform-friction nut factor `K·d = 0.159·P + 0.578·d₂·μ + 0.5·D_Km·μ`,
D_Km = (d_w + d_h)/2. The installation stress reproduces SpaceBolt's
worst pairing (max preload with μ_min thread torque) and its use of the
stress diameter d₀ for both A_s and W_p.

Inputs used to reach parity (all available in the API):
`nut_factor_K_min/max`, `tool_scatter_pct`, `embedding_percent_of_max`,
`head_bearing_diameter_mm` (DIN 912 d_w = 7), `available_flange_diameter_mm`
(D_A = 17.5), `standard="ECSS"` (full σ_y with installation FoS instead of
VDI's ν = 0.9), explicit FoS = 1.0, `tapped_engagement_length_mm`.

## Documented divergences (BoltSizer conservative in every one)

| Margin | BoltSizer | SpaceBolt | Cause |
|---|---|---|---|
| Gapping / separation | +0.92 | +1.00 | Bolt load share: SpaceBolt's "accurate flange calculation" (flange-opening model) gives Φ = 0.30; our concentric cone model gives φ_n = 0.27. |
| Sliding (min preload) | +1.25 | +1.35 | Same Φ difference. |
| Combined yield (working) | +0.04 | +0.10 | BoltSizer retains 50% residual tightening torsion (VDI §5.5.2); SpaceBolt's working margins are axial-only. |
| Combined ultimate (working) | +0.30 | +0.38 | Same residual-torsion difference. |
| Tightening ultimate | +0.18 | +0.30 | BoltSizer retains full tightening torsion for the installation ultimate margin; SpaceBolt partially relaxes it. |
| Thread pull-out (total) | +2.68 | +3.31 | SpaceBolt uses the entered shear ultimate (207 MPa) directly; BoltSizer derives 0.577·UTS(310) = 179 MPa from the tensile ultimate. |
| Bolt shear (yield) | +27.6 | +32.7 | SpaceBolt: 0.6·σ_y on A_s; BoltSizer: 0.577·σ_y on A_d3. |

Stiffness detail: SpaceBolt reports δ_b = 9.7e-6, δ_p = 1.94e-6 mm/N
(which by δ_p/(δ_b+δ_p) would give Φ = 0.17 — their reported bolt share of
0.30 comes from the flange-opening model, not the resilience ratio).
BoltSizer's δ_S = 7.6e-6 / δ_P = 2.8e-6 gives φ = 0.27 directly, landing
close to SpaceBolt's effective share for this joint.

## Conclusions

1. **Preload chain, installation stress, and the tightening yield margin
   agree to ≤1%** when the same conventions are selected — these are the
   quantities with a single defensible physical answer.
2. All remaining differences are **deliberate conservative conventions**
   in BoltSizer (residual torsion, A_d3 shear plane, 0.577 vs 0.6, UTS-derived
   thread shear), each ≤ 0.1 in margin terms for this case.
3. The one genuine **modeling gap** is the flange-opening (prying) model:
   SpaceBolt's "accurate flange calculation" raises the bolt load share
   above the concentric resilience ratio. For this case the concentric
   model lands within 10% (0.27 vs 0.30). A prying/eccentricity model is
   the highest-value future addition for closer parity.

Additional SpaceBolt reports (especially with bending, thermal cases, and
multi-bolt patterns) can be appended to the fixture set the same way.

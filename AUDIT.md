# BoltSizer Calculation Audit

**Date:** 2026-08-09
**Scope:** All calculation modules, sizing methods, data tables, and modeling assumptions in
`boltsizer/`, plus the API and UI layers where they touch numbers.
**Verdict:** The architecture and analysis flow are sound, but the tool is **not yet fit for
internal design use**. There are 6 critical defects — including one dimensional error that
corrupts every downstream margin, and several non-conservative errors that overstate margins.
The test suite (46 passing) is self-referential and cannot catch any of them.

---

## FIX STATUS (2026-08-09, same branch)

All findings below have been **implemented and fixed** in the follow-up commit on this
branch, with reference validation tests added (`tests/test_validation.py`):

| Finding | Status |
|---|---|
| C1 cone compliance (dimensional) | ✅ Fixed — closed-form frustum with d_h, opposed cones meeting at mid-grip, per-layer piecewise integration, optional D_A cap. δ_P matches hand calc to 1e-9; φ = 0.174 for the M12 steel reference joint. |
| C2 embedding loss | ✅ Fixed — F_Z = f_Z/(δ_S+δ_P); stiffness computed before preload; VDI Table 5.4 per-region guide values (axial/shear rows). |
| C3 ECSS separation convention | ✅ Fixed — both conventions use after-loss preload; ECSS applies a separation FoS (default 1.2). Wrong test replaced. |
| C4 fatigue allowables | ✅ Fixed — VDI σ_ASV = 0.85·(150/d+45), σ_ASG for rolled-after-HT; smooth-bar limits removed from the library (user override only for fastener test data). |
| C5 API PDF export | ✅ Fixed — correct signature + report metadata; verified end-to-end (returns valid PDF). |
| C6 torsion ignored | ✅ Fixed — V_t = M_T/(n_B·r) added to per-bolt shear (conservative scalar sum); degenerate-pattern warning. |
| H1 bolt compliance | ✅ Fixed — full VDI §5.1.1 terms (head/shank/thread/engaged/nut, A_N vs A_d3), lengths reconciled with the grip; shank>grip warning. |
| H2 assembly torsion | ✅ Fixed — μ derived from K decomposition, M_G and τ in assembly yield; 50% residual torsion in working yield/ultimate. |
| H3 scatter convention | ✅ Fixed — symmetric scatter F_nom·(1±ε), ε=(α−1)/(α+1); optional K_min/K_max envelope. |
| H4 data tables | ✅ Fixed — M20x1.5 + all Unified A_s corrected; ISO 8.8 ≤M16/>M16 split; 10.9→940, 12.9→1100; d_w (ISO 4014) and holes (ISO 273) added; bearing areas recomputed. Self-consistency tests added. |
| H5 missing checks | ✅ Implemented — surface pressure under head, ultimate margins (FOSU), thread stripping (tapped joints), thermal preload change (CTE per material, ΔT per case). ECSS FoS defaults wired (1.1/1.25/1.2). |
| M1–M9 | ✅ Fixed — fatigue min/max load set, load_plane wired to n, per-bolt self-loosening warning, preview uses real stack, Custom grade validated (400 without properties), shear on A_d3 with 0.577 + ultimate, embedding table per-region, tests replaced with reference validation. |

Remaining known limitations (documented, not defects): cone half-angle fixed at 30° by
default (configurable), Unified d_w/d_h use documented fallback estimates, bearing allowable
remains the 1.5·σ_y convention, prying/eccentricity not modeled. Validate against SpaceBolt
reports before production use.

Severity legend:
- **CRITICAL** — produces wrong numbers in normal use, or a non-conservative safety error.
- **HIGH** — deviates from VDI 2230 / ECSS-E-HB-32-23 in a way that will not match reference
  tools (e.g. SpaceBolt) or is non-conservative in edge cases.
- **MEDIUM** — inconsistency, dead input, or convention mismatch that misleads the user.
- **LOW** — cosmetic / documentation.

---

## 1. CRITICAL findings

### C1. Rotscher pressure-cone compliance is dimensionally wrong (~9× too compliant)
`boltsizer/calculations/joint_stiffness.py:129`

```python
delta_layer = math.log(num / den) / (E * math.pi * tan_phi)
```

Three separate errors versus the standard frustum formula
(Shigley §8-5; equivalent to VDI 2230 §5.1.2 cone model):

1. **Missing `d_h` in the denominator.** The correct expression is
   `ln(...) / (π · E · d_h · tanφ)`. Since `ln(...)` is dimensionless, the implemented
   expression has units mm²/N, not mm/N — it fails dimensional analysis. δ_P is inflated by a
   factor of roughly the hole diameter in mm (≈8–30×).
2. **Cone-spread term uses `l·tanφ` instead of `2·l·tanφ`.** The standard frustum term is
   `2·t·tanφ + d_w ± d_h`.
3. **Cone topology.** Each layer restarts its own cone at `d_w`. The correct model for a
   through-bolted joint is two opposed cones growing from head and nut bearing faces and
   meeting at mid-grip. For a single-layer joint the code produces one full-length cone from
   one side, which is wrong even topologically. (For two equal layers the layer split happens
   to coincide with the mid-plane, so only errors 1–2 apply there.)

**Quantified impact** (M12 ISO 8.8, two 20 mm steel plates, defaults):

| Quantity | Code | Correct | Note |
|---|---|---|---|
| δ_P | 3.92e-6 mm/N | 4.41e-7 mm/N | 8.9× too compliant |
| φ (basic) | **0.667** | **≈0.13** | typical steel joints: 0.1–0.35 |

Because φ = δ_P/(δ_S+δ_P) feeds *everything*:
- Bolt max load & fatigue amplitude overstated ~5× (conservative direction),
- **Joint separation demand `F_ext·(1−φ_n)` and slip clamp-loss understated
  (non-conservative)** — separation and slip margins are overstated.

**Fix:** implement the frustum stack correctly (per-layer frusta with cone continuation and
mirror at mid-grip, divide by `d_h`, use `2t·tanφ`), or better, implement VDI 2230 §5.1.2.2
substitution-area equations (Eq. 5.10–5.12) with the D_A limitation. Note: there is currently
**no input for the available flange outer diameter / bolt spacing**, so the cone can spread
indefinitely — D_A limiting needs a new input (min(bolt pitch, 2×edge distance)).

### C2. Embedding loss uses bolt stiffness only instead of joint stiffness
`boltsizer/calculations/preload.py:110`

```python
F_Z = (f_Z * E_S * A_s / grip_length)
```

VDI 2230 (2014) Eq. (5.4.2.1): **F_Z = f_Z / (δ_S + δ_P)**. The preload loss from embedding
is resisted by the series stiffness of bolt *and* clamped parts. Using `E·A_s/l_K`
(≈ 1/δ_S of the threaded shank alone) overestimates F_Z by (δ_S+δ_P)/δ_S ≈ 1.5× in the
reference case. Conservative direction, but wrong, and will not reconcile with SpaceBolt.
Note the current architecture computes preload before stiffness
(`vdi2230.py:197-200`); the fix requires passing δ_S+δ_P into `calculate_preload`.

### C3. ECSS separation convention is backwards (non-conservative), and a test locks it in
`boltsizer/calculations/failure_modes.py:205-206`, `boltsizer/ecss/ecss_hb_32_23.py:27-44`,
`tests/test_failure_modes.py:110-121`

```python
if standard == "ECSS":
    F_V_min = preload.F_M_min  # ECSS: without embedding (conservative)
```

Using the minimum preload *without* subtracting the embedding loss yields a **higher**
allowable clamping force and therefore a **higher (optimistic) separation margin**. That is
anti-conservative, and it is not what ECSS-E-HB-32-23 does — the handbook's minimum preload
explicitly subtracts all preload losses (embedding, thermal). The docstrings in both files
assert "conservative" for a change in the optimistic direction, and
`test_ecss_uses_FM_min_not_net` enshrines the behavior (its own inline comments visibly
contradict themselves). Also inconsistent: the ECSS branch changes separation but `check_slip`
still uses `F_preload_min` regardless of standard.

**Fix:** ECSS mode must use preload minus losses (same direction as VDI), plus the ECSS
scatter convention (see H3). Delete/fix the test.

### C4. Material fatigue limits are smooth-bar values, not bolt-thread values (2.5–6× optimistic)
`boltsizer/standards/material_library.py` (`fatigue_limit` entries),
used by `failure_modes.py:check_fatigue`

The check compares the bolt stress amplitude directly with `material.fatigue_limit`:
129 MPa (8.8), 150 (10.9), 170 (12.9), 380 (A286), 450 (Inconel 718), 340–350 (Ti-6Al-4V).
These are smooth-specimen magnitudes. Rolled-thread fastener endurance per
VDI 2230 §5.5.3 (rolled before heat treatment) is:

σ_ASV = 0.85·(150/d + 45)  →  ≈ 49 MPa for M12, ≈ 51 MPa for M10 — largely
**independent of grade**. The library values overstate the fatigue allowable by roughly
2.5× (ISO grades) to ~5× (aerospace alloys, where 380–450 MPa is far above any threaded
fastener allowable). **The fatigue margin is grossly non-conservative.** It happens to be
partially masked today by C1 inflating the amplitude ~5×; fixing C1 without fixing C4 would
make fatigue margins wildly optimistic.

**Fix:** compute σ_AS per VDI 2230 (diameter-dependent, rolled-before/after-HT switch:
σ_ASG = (2 − F_Sm/F_0.2min)·σ_ASV for rolled after HT), or use fastener-specific S-N data.
A per-material scalar cannot represent thread fatigue.

### C5. API PDF export is broken — wrong call signature
`api/main.py:396` vs `boltsizer/export/pdf_report.py:46`

```python
pdf_bytes = generate_pdf_report(bc, iface, results)          # api/main.py
def generate_pdf_report(results, bolt_cfg, joint_cfg, report_meta)   # actual signature
```

Every call to `POST /api/export/pdf` raises `TypeError` (surfaced as HTTP 500). The React
app's PDF export cannot ever have worked. (The legacy Streamlit page `pages/05_Report.py:61`
calls it correctly with keywords.)

### C6. Torsion input is collected then silently ignored
`frontend/src/pages/Loading.tsx:104-111` → `api/main.py:321` →
`boltsizer/calculations/load_distribution.py` (never reads `loading.torsion`)

The UI offers "Torsion M_T [N·mm]", the API forwards it into `ExternalLoading.torsion`, and
the load distribution never uses it. Torsion about the bolt-circle axis adds per-bolt shear
`V_t = M_T·γ/(n_B·r)` (to be combined vectorially with the direct-shear share). Any case
with torsion silently under-reports bolt shear → **non-conservative slip, bolt-shear and
bearing margins**. Either implement it or remove the input; silent discard is the worst option.

---

## 2. HIGH findings

### H1. Bolt compliance δ_S deviates from VDI 2230 §5.1.1 (~30% low) and ignores the grip
`boltsizer/calculations/joint_stiffness.py:38-75`

- The function receives `grip_length` and **never uses it**. It sums user-supplied
  `shank_length` + `threaded_length`, which need not equal l_K — the shipped defaults
  (20 + 15 = 35 mm vs grip 40 mm) already disagree. δ_S and δ_P then describe two different
  joints, and φ is meaningless to that extent. The free loaded length inside the grip must
  reconcile to l_K.
- Free loaded thread should use the minor-diameter area A_d3, not A_s.
- Head substitution length (0.4·d) should use the nominal area A_N, not A_s.
- Missing terms: engaged thread l_G = 0.5·d over A_d3 and nut/engaged region l_M = 0.4·d
  over A_N.

Reference case: δ_S = 1.96e-6 (code) vs 2.87e-6 mm/N (VDI) — ~32% underestimate → overstates
bolt stiffness → shifts φ upward (compounds C1's direction).

### H2. Assembly torsional stress is never actually applied
`boltsizer/calculations/failure_modes.py:117-177, 433, 447`

`check_yield_combined` supports `M_torsion_thread`, but `calculate_all_margins` defaults it
to 0 and nothing anywhere computes the thread torque
`M_G = F_M·(0.16·P + 0.58·d₂·μ_G)`. So both yield checks reduce to axial-only during/after
assembly. VDI 2230 §5.5.1 requires σ_red = √(σ_M² + 3τ²) ≤ ν·R_p0.2 at assembly — torsion
typically adds 20–40% to the equivalent stress. As shipped, "Yield at Assembly" (0.9×proof,
axial only) is the only guard, and it is **non-conservative** relative to the standard.
Compute M_G from the K-factor decomposition (or ask for μ_th) and feed it in.

### H3. Preload scatter convention is mixed and one-sided
`boltsizer/calculations/preload.py:88-100`, `boltsizer/standards/nut_factors.py`

- `F_M_max = M_A/(K_nom·d)` and `F_M_min = F_M_max/α_A`. Treating the *nominal-friction*
  torque conversion as the **maximum** preload is unsafe: with friction at the low end of the
  coating's range, actual preload at the same torque exceeds M_A/(K_nom·d), so the
  yield-at-assembly check is non-conservative. `NUT_FACTOR_TABLE` carries `K_min/K_max`
  for every coating and **never uses them** (`get_nut_factor` returns only nominal).
  Proper bracketing: F_M_max from K_min, F_M_min from K_max (and/or α_A).
- ECSS/SpaceBolt convention is symmetric scatter about nominal
  (F_nom·(1+ε) / F_nom·(1−ε)); the VDI α_A convention here divides down only. Expect
  systematic disagreement with SpaceBolt min/max preloads until the convention is selectable.
- `impact_wrench` α_A = 2.0; VDI guide values are 2.5–4 → non-conservative table entry.

### H4. Data-table errors (verified against ISO 898-1 / ISO 724 / ASME B1.1)
`boltsizer/standards/bolt_library.py`, `material_library.py`

Stress areas (A_s), checked numerically:

| Entry | Listed | Correct | Error |
|---|---|---|---|
| M20x1.5 | 259.0 | 272 mm² | −4.6% (looks like the M20x2 value) |
| 1/4-28 UNF | 22.00 | 23.48 mm² | −6.3% |
| 5/16-18 UNC | 34.63 | 33.83 mm² | **+2.4% (non-conservative)** |
| 3/8-16 UNC | 52.00 | 50.0 mm² | **+4.0% (non-conservative)** |
| 7/16-14 UNC | 71.60 | 68.6 mm² | **+4.4% (non-conservative)** |
| 1/2-13 UNC | 93.50 | 91.5 mm² | **+2.1% (non-conservative)** |

All other ISO coarse/fine and UNF entries agree within ±0.4%.

Materials:
- **ISO 8.8**: proof stress listed 600 MPa — ISO 898-1 gives **580 for ≤M16** (600 applies
  only above M16); yield 640 is the ≤M16 value (660 above M16). The library is
  size-independent, so one side is always wrong; as shipped the proof stress is
  non-conservative for the common ≤M16 range.
- ISO 10.9 yield listed 900 vs standard min 940; 12.9 listed 1080 vs 1100 (both conservative).
- `head_bearing_area` values (≈A_s, e.g. 37 mm² for M8) contradict the file's own comment
  formula π/4·(d_w²−d_h²) (≈63 mm² for M8). Currently unused by any calculation — a trap for
  whoever wires up the missing surface-pressure check (see H5).

### H5. Checks promised or expected but missing
- **Surface pressure under head/nut** (VDI 2230 §5.5.4, listed as "R8" in
  `vdi2230.py`'s own docstring): not implemented; `head_bearing_area` unused. Critical for
  aluminium/CFRP flanges, which the material list explicitly supports.
- **Thread shear / stripping & minimum engagement length** (VDI 2230 §5.5.5,
  ECSS-E-HB-32-23 §7.15): absent. No nut/tapped-thread inputs exist.
- **Ultimate-strength margins**: ECSS requires yield *and* ultimate checks with separate
  FoS (FOSY 1.1 / FOSU 1.25 typical). Only yield-based checks exist; `uts` is stored and
  never used. `ECSS_LOAD_FACTORS` and `ecss_minimum_preload()` in
  `boltsizer/ecss/ecss_hb_32_23.py` are dead code — no factor is ever applied unless the
  user manually bakes it into `load_factor`.
- **Thermal preload loss** (ΔF from CTE mismatch): explicitly out of scope per the PDF
  assumptions, but for a space-hardware tool (A286/Ti/Inconel on Al flanges) this is usually
  a dominant loss term; SpaceBolt reports will include it.

---

## 3. MEDIUM findings

- **M1 — Fatigue amplitude semantics.** `check_fatigue` computes
  `F_SA = φ_n·F_ext/2`, i.e. assumes pure pulsating (0→max) cycling, but its docstring says
  "for fully reversed loading, = F_ext_max" — under that reading the /2 is a 2×
  non-conservative error. There is no R-ratio/min-max input to disambiguate
  (`failure_modes.py:373-420`, duplicated at `vdi2230.py:216`). Define load-case min/max and
  compute F_SA = φ_n·(F_max−F_min)/2 explicitly.
- **M2 — `load_plane` is a dead field.** `ExternalLoading.load_plane`
  ("interface"/"bolt_head") is set by the Streamlit UI but never read; the load-introduction
  factor n is a separate global input. Users will believe the toggle does something.
- **M3 — Self-loosening warning mixes totals and per-bolt.** `vdi2230.py:160` compares the
  *total* circle shear against the *per-bolt* min preload → over-warns by n_B×.
- **M4 — Preload preview uses a hard-coded grip.** `frontend/src/pages/BoltSelection.tsx:71`
  sends `grip_length_mm: 40` regardless of the actual stack, so the page-1 F_Z / net-preload
  preview disagrees with the final analysis for any other grip.
- **M5 — "Custom" grade silently becomes ISO 8.8.** `api/main.py:169` substitutes ISO 8.8
  when grade == "Custom" (and the library "Custom" entry is all zeros anyway). Silent
  substitution of material properties in a sizing tool is dangerous — reject or accept
  explicit user properties.
- **M6 — Shear/bearing allowables are yield-based conventions.**
  0.6·A_s·σ_y (shear) and 1.5·σ_y·d·t (bearing) are structural-steel conventions; ECSS-style
  margins use ultimate-based allowables (τ_allow ≈ 0.577·σ_u, bearing on σ_u with FoS) —
  another source of systematic disagreement with SpaceBolt. Shear should also use the shank
  area A_N when the shear plane is in the shank (plane selection input missing).
- **M7 — Hole and bearing diameters hard-coded.** `d_h = d` (zero clearance) and
  `d_w = 1.5·d` in `joint_stiffness.py:167-168`; no washer or hole-class inputs. Clearance
  holes (ISO 273 medium: e.g. 13.5 mm for M12) change the cone and bearing area.
- **M8 — Embedding table provenance.** `_EMBEDDING_TABLE` is a matrix over
  (interfaces × Rz), while VDI 2230 Table 5.4/5.5 gives per-region guide values (thread +
  per head/nut interface + per inner interface) by Rz and load type. The magnitudes are
  plausible but not traceable to the cited table; `num_mating_surfaces` also excludes the
  thread/head contributions the standard counts.
- **M9 — Test suite is self-referential.** Nearly every assertion re-derives the expected
  value *from the same formula the code uses* (e.g. `test_shear_capacity_formula`,
  `test_fatigue_amplitude_formula`). The only external anchors are the two JSON fixtures,
  which validate nothing beyond `F_M = M_A/(K·d)`. None of C1–C4 can be caught by this
  suite; C3 is actively asserted as correct. Priority: add reference cases with known
  results (VDI 2230 worked example; the promised SpaceBolt reports are ideal).

---

## 4. LOW / cosmetic

- `F_M = M_A/(K·d)` is cited as "VDI 2230 Eq. (5.1)" throughout — VDI 2230 has no K-factor;
  it uses the full torque decomposition (its Eq. 5.4/1). The K-factor shortcut is
  Bickford / NASA-STD-5020. Same mis-citation for "Table A5" (tightening factors are
  Table A8 in VDI 2230-1:2015) — worth re-checking every citation before this goes in
  reports, since the PDF export prints them.
- `check_yield_combined` uses W_p = π·d3³/16 (minor diameter). VDI uses d_s = (d₂+d₃)/2
  consistently for both A_s and W_p; using d3 is slightly conservative. Its LaTeX string
  also doesn't match the computed expression.
- `_build_calc_steps` R1 always says "Preload from assembly torque" even in target-preload
  mode.
- `torque_angle` α_A = 1.2 is the optimistic edge of the VDI 1.2–1.4 guide band.
- `binding` flag logic duplicated between `calculate_all_margins` (sort + flag) and
  `BoltResults.binding_margin` (min) — keep one source of truth.

---

## 5. What is correct (verified)

- Bending distribution `F_B,i = M·r·cosθ_i / Σ r_j²cos²θ_j` reduces to the standard
  `F_max = 2M/(n·r) = 4M/(n·D)` for n ≥ 3 — correct for the rigid-flange/elastic-bolt
  assumption (verified numerically).
- Axial and shear equal-share distribution, load-factor application, critical-bolt
  selection: correct.
- φ = δ_P/(δ_S+δ_P), φ_n = n·φ and the separation criterion form
  `F_V ≥ (1−φ_n)·F_ext`: correct structure (inputs to them are not — C1/C2).
- Margin definition MS = allowable/applied − 1, worst-first sorting, binding flag: correct.
- ISO coarse-thread A_s, d₂, d₃ tables: all within ±0.4% of ISO 724/898-1 (verified
  numerically). Most fine-pitch and UNF entries likewise (exceptions in H4).
- Torque→preload conversion and direct-preload mode plumbing, embedding-table monotonicity,
  and the API serialization layer (aside from C5): correct.

---

## 6. Recommended fix order

1. **C1 + H1** — rebuild `joint_stiffness.py` per VDI 2230 §5.1 (this unblocks everything;
   φ must land in the physically sane 0.1–0.35 band for steel-on-steel reference joints).
   Add flange outer diameter / bolt-pitch input for D_A limiting.
2. **C2** — embedding as f_Z/(δ_S+δ_P) (needs stiffness computed before preload losses).
3. **C3** — ECSS minimum preload = after losses; align `check_slip`; fix the test.
4. **C4** — VDI thread-fatigue allowables (d-dependent, rolled before/after HT).
5. **C6 / H2 / H3** — torsion shear, thread-torque in yield checks, K_min/K_max bracketing.
6. **C5, M4, M5** — API/UI plumbing fixes.
7. **H4** — table corrections (M20x1.5, UNC entries, 8.8 proof stress size split).
8. **H5** — missing checks (surface pressure, thread stripping, ultimate margins, thermal).
9. **M9** — validation tests against SpaceBolt / VDI worked examples once conventions align.

A note on validation strategy: several errors currently *cancel partially* (C1 inflates the
fatigue amplitude while C4 inflates the allowable; C1 is conservative for bolt load but
non-conservative for separation). Fixing any one in isolation can make headline margins move
in surprising directions — fix C1–C4 as a batch, then validate against the SpaceBolt reports.

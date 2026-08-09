# BoltSizer

Bolted-joint analysis and sizing for engineering teams — **VDI 2230 Part 1
(2014)** methodology with optional **ECSS-E-HB-32-23A** conventions and
factors of safety. React frontend, FastAPI backend, pure-Python
calculation engine.

> **Validation status:** the engine is cross-validated against a
> SpaceBolt™ v2.2 reference report — preload chain, embedding loss and
> installation stress agree to ≤1% with matching conventions; all
> remaining margin differences are documented conservative conventions.
> See [`VALIDATION.md`](VALIDATION.md) and [`AUDIT.md`](AUDIT.md).

## Quickstart

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
./start_react.sh
# React app:  http://localhost:5173
# API docs:   http://localhost:8000/docs
```

## What it does

Five-step workflow: **Bolt Selection → Joint Geometry → Loading →
Results → Report**, with live preload and stiffness previews while you
type, and a global Run button.

Checks per load case (each with allowable, applied, MS, binding flag and
the substituted formula):

| Check | Basis |
|---|---|
| Yield / Ultimate at assembly | von Mises incl. tightening torsion (VDI §5.5.1) |
| Yield / Ultimate at working load | 50% residual torsion (VDI §5.5.2), FOSY/FOSU |
| Joint separation (gapping) | after ALL preload losses, separation FoS |
| Interface slip | residual clamp × μ × n_i |
| Bolt shear (yield + ultimate) | 0.577·σ on A_d3 (or shank) |
| Plate bearing, head surface pressure | 1.5·σ_y / p_G limit |
| Fatigue (infinite life) | VDI thread endurance σ_ASV/σ_ASG, cycle min/max |
| Thread stripping | tapped joints, internal/external shear areas |

Engine features: symmetric tightening scatter (α_A) **or** friction-range
bracketing (K_min/K_max × tool scatter, ECSS/SpaceBolt convention),
embedding per VDI Table 5.4 or %-of-preload, thermal preload change from
CTE mismatch (ΔT per load case), compression-cone stiffness with D_A
limit, torsion-induced bolt shear, per-case load-introduction plane.

## Data libraries

- **Bolts:** ISO metric coarse/fine (M3–M36) and Unified UNC/UNF, with
  ISO 4014 washer-face and ISO 273 clearance-hole diameters
  (`boltsizer/standards/bolt_library.py`). Add a size by appending one
  table row — a self-consistency test recomputes every entry from the
  standard formulas.
- **Materials:** ISO 898-1 grades (size-dependent minimums), A2/A4
  stainless, A286, Inconel 718, Ti-6Al-4V, plus fully custom properties
  (`material_library.py`). Thread fatigue allowables are *computed* per
  VDI 2230 §5.5.3 — never stored smooth-bar values.
- **Nut factors:** coating/lubrication table with K nominal + range;
  VDI Table A8 tightening-scatter factors.

## Development

```bash
python -m pytest tests/            # 97+ tests incl. reference validation
cd frontend && npx tsc -b          # type-check
```

CI runs pytest + tsc + build on every push/PR (`.github/workflows/ci.yml`).

Layout:

```
boltsizer/           calculation engine (pure functions, SI units: N, mm, MPa)
  calculations/      preload, stiffness, load distribution, failure modes, orchestrator
  standards/         bolt / material / nut-factor tables
  ecss/              ECSS FoS conventions
  export/            PDF calculation note (ReportLab)
api/main.py          FastAPI backend
frontend/            React + Blueprint UI (Vite)
tests/               engine tests + SpaceBolt validation fixtures
```

The former Streamlit UI was removed (2026-08) to keep a single frontend —
recover it from git history if ever needed.

## Sizing & depth features

- **Torque window finder** — sweeps M_A, shades the allowable band
  (floor: separation/slip; ceiling: assembly yield/surface pressure) and
  recommends the max-worst-margin torque.
- **Bolt auto-suggest** — evaluates every same-standard library size via
  its torque window; smallest passing size at a glance.
- **Sensitivity tornado** — one-at-a-time perturbations (μ, K, torque,
  loads, ΔT) ranked by influence on the worst margin.
- **Patterns** — bolt circle, rectangular grid, or custom XY positions
  (bending about the centroid, torsion ∝ radius).
- **Eccentric clamping/loading** — simplified VDI 2230 §5.3.2 model
  (s_sym, a inputs); a > s produces prying and raises the bolt share.
- **Multi-group projects** — save named bolt groups and export one
  project PDF with an overall summary of margins.

## Scope & assumptions

Compression-cone half-angle 30° default, substitutional-solid inertia
for the eccentric model approximated as an annulus of the effective
solid diameter, bearing allowable 1.5·σ_y convention, shear direction
vs pattern not tracked (conservative scalar combination). All results
are engineering estimates — verify against applicable project standards.

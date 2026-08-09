"""BoltSizer FastAPI backend.

Exposes the boltsizer calculation engine as a REST API for the React frontend.
All values in SI units: N, mm, MPa unless noted.
"""
from __future__ import annotations
import sys
import os
import json
import io
from typing import List, Optional, Literal

# Add project root to path so boltsizer package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from boltsizer.standards.bolt_library import BOLT_LIBRARY
from boltsizer.standards.material_library import MATERIAL_LIBRARY, FLANGE_MATERIAL_E
from boltsizer.standards.nut_factors import NUT_FACTOR_TABLE, TIGHTENING_SCATTER, TIGHTENING_METHOD_LABELS
from boltsizer.standards import get_bolt_geometry, get_material
from boltsizer.models.bolt import Bolt, BoltMaterial
from boltsizer.models.joint import BoltCircle, ClampedInterface, ClampedLayer, ExternalLoading
from boltsizer.calculations.preload import calculate_preload
from boltsizer.calculations.joint_stiffness import calculate_joint_stiffness
from boltsizer.calculations.vdi2230 import run_vdi2230_analysis
from boltsizer.calculations.sizing import torque_window, suggest_bolts, sensitivity
from boltsizer.export.pdf_report import generate_pdf_report, generate_project_pdf
from boltsizer import __version__ as ENGINE_VERSION

app = FastAPI(title="BoltSizer API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Reference data endpoints
# ---------------------------------------------------------------------------

@app.get("/api/bolts")
def get_bolts():
    """Return the full bolt library."""
    return BOLT_LIBRARY


@app.get("/api/materials")
def get_materials():
    """Return bolt material library."""
    return MATERIAL_LIBRARY


@app.get("/api/coatings")
def get_coatings():
    """Return coating/lubrication K-factor table."""
    result = {}
    for key, (k_nom, k_min, k_max, desc) in NUT_FACTOR_TABLE.items():
        result[key] = {"k_nom": k_nom, "k_min": k_min, "k_max": k_max, "description": desc}
    return result


@app.get("/api/tightening-methods")
def get_tightening_methods():
    """Return tightening methods with scatter factors and labels."""
    result = {}
    for key, (alpha_A, desc) in TIGHTENING_SCATTER.items():
        result[key] = {
            "alpha_A": alpha_A,
            "description": desc,
            "label": TIGHTENING_METHOD_LABELS.get(key, key),
        }
    return result


@app.get("/api/flange-materials")
def get_flange_materials():
    """Return flange/clamped-part material Young's moduli."""
    return FLANGE_MATERIAL_E


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CustomMaterial(BaseModel):
    """Explicit material properties for grade == 'Custom'."""
    yield_strength_MPa: float
    uts_MPa: float
    youngs_modulus_MPa: float = 210000.0
    proof_load_stress_MPa: Optional[float] = None
    fatigue_limit_MPa: Optional[float] = None   # fastener-specific data only
    cte_per_K: Optional[float] = None


class _BoltFields(BaseModel):
    designation: str
    grade: str
    shank_length_mm: float = 20.0
    threaded_length_mm: float = 15.0
    nut_factor_K: float = 0.16
    nut_factor_K_min: Optional[float] = None
    nut_factor_K_max: Optional[float] = None
    tool_scatter_pct: Optional[float] = None       # e.g. 0.05 for ±5% torque tool
    assembly_torque_Nmm: float = 0.0
    target_preload_N: float = 0.0
    tightening_method: str = "torque_wrench"
    num_mating_surfaces: int = 2
    surface_roughness_Rz: float = 6.3
    embedding_percent_of_max: Optional[float] = None  # e.g. 0.05 → F_Z = 5%·F_M_max
    thread_rolled: Literal["before_ht", "after_ht"] = "before_ht"
    head_bearing_diameter_mm: Optional[float] = None  # override d_w (e.g. DIN 912)
    hole_diameter_mm: Optional[float] = None          # override clearance hole d_h
    custom_material: Optional[CustomMaterial] = None


class PreloadPreviewRequest(_BoltFields):
    grip_length_mm: float = 40.0
    # Optional layer stack — enables the correct embedding loss
    # F_Z = f_Z/(δ_S+δ_P); without it a single steel layer of the grip
    # length is assumed for the preview.
    layers: Optional[List[dict]] = None


class StiffnessPreviewRequest(_BoltFields):
    # Joint
    num_bolts: int = 8
    bolt_circle_diameter_mm: float = 100.0
    layers: List[dict] = Field(default_factory=lambda: [{"material": "Steel (carbon)", "thickness_mm": 20.0, "E": 210000.0}])
    interface_treatment: str = "bare metal"
    friction_coefficient: float = 0.12
    num_friction_interfaces: int = 1
    load_intro_factor_n: float = 0.5
    available_flange_diameter_mm: Optional[float] = None
    cone_half_angle_deg: float = 30.0
    eccentricity_s_mm: float = 0.0
    load_eccentricity_a_mm: float = 0.0


class LoadCaseRequest(BaseModel):
    case_name: str = "LC1"
    axial_force_N: float = 0.0
    bending_moment_Nmm: float = 0.0
    shear_force_N: float = 0.0
    torsion_Nmm: float = 0.0
    axial_force_min_N: float = 0.0
    bending_moment_min_Nmm: float = 0.0
    delta_T_C: float = 0.0
    load_plane: Literal["interface", "bolt_head"] = "interface"
    load_factor: float = 1.0


class ReportMeta(BaseModel):
    project_name: str = ""
    revision: str = "A"
    engineer_name: str = ""


class AnalyzeRequest(_BoltFields):
    # Joint geometry
    num_bolts: int = 8
    bolt_circle_diameter_mm: float = 100.0
    # Bolt pattern (default circle keeps historical behaviour)
    pattern: Literal["circle", "rectangle", "custom"] = "circle"
    rect_nx: int = 2
    rect_ny: int = 2
    rect_pitch_x_mm: float = 60.0
    rect_pitch_y_mm: float = 60.0
    custom_positions_mm: Optional[List[List[float]]] = None  # [[x, y], ...]
    layers: List[dict] = Field(default_factory=lambda: [{"material": "Steel (carbon)", "thickness_mm": 20.0, "E": 210000.0}])
    interface_treatment: str = "bare metal"
    friction_coefficient: float = 0.12
    num_friction_interfaces: int = 1
    load_intro_factor_n: float = 0.5
    available_flange_diameter_mm: Optional[float] = None
    cone_half_angle_deg: float = 30.0
    # Eccentric clamping / loading (VDI 2230 §5.3.2); 0 = concentric
    eccentricity_s_mm: float = 0.0
    load_eccentricity_a_mm: float = 0.0
    plate_thickness_mm: float = 20.0
    plate_yield_strength_MPa: float = 240.0
    surface_pressure_limit_MPa: Optional[float] = None
    shear_plane_in_threads: bool = True
    # Tapped joint (no nut): both required to enable the stripping check
    tapped_engagement_length_mm: Optional[float] = None
    tapped_material_uts_MPa: Optional[float] = None
    # Factors of safety — None → defaults for the chosen standard
    fos_yield: Optional[float] = None
    fos_ultimate: Optional[float] = None
    fos_separation: Optional[float] = None
    fos_slip: Optional[float] = None
    fos_yield_installation: float = 1.0
    fos_ultimate_installation: float = 1.0
    # Load cases
    load_cases: List[LoadCaseRequest] = Field(default_factory=lambda: [LoadCaseRequest()])
    standard: Literal["VDI", "ECSS"] = "VDI"
    report_meta: Optional[ReportMeta] = None


# ---------------------------------------------------------------------------
# Helper: build Python objects from request dicts
# ---------------------------------------------------------------------------

def _build_material(req: _BoltFields, nominal_diameter: float) -> BoltMaterial:
    if req.grade == "Custom":
        if req.custom_material is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Grade 'Custom' requires explicit material properties "
                    "(custom_material: yield_strength_MPa, uts_MPa, ...)."
                ),
            )
        cm = req.custom_material
        if cm.yield_strength_MPa <= 0 or cm.uts_MPa <= 0:
            raise HTTPException(
                status_code=400,
                detail="Custom material yield/UTS must be positive.",
            )
        return BoltMaterial(
            name="Custom",
            yield_strength=cm.yield_strength_MPa,
            uts=cm.uts_MPa,
            youngs_modulus=cm.youngs_modulus_MPa,
            fatigue_limit=cm.fatigue_limit_MPa,
            proof_load_stress=cm.proof_load_stress_MPa,
            cte=cm.cte_per_K,
        )
    return get_material(req.grade, nominal_diameter)


def _build_bolt_circle(req: _BoltFields, num_bolts: int = 1, pcd: float = 0.0) -> BoltCircle:
    import math as _math
    geom = get_bolt_geometry(req.designation, req.shank_length_mm, req.threaded_length_mm)
    # Optional geometry overrides (e.g. DIN 912 socket head d_w, custom hole)
    if req.head_bearing_diameter_mm is not None and req.head_bearing_diameter_mm > 0:
        geom.head_bearing_diameter = req.head_bearing_diameter_mm
    if req.hole_diameter_mm is not None and req.hole_diameter_mm > 0:
        geom.hole_diameter = req.hole_diameter_mm
    if req.head_bearing_diameter_mm is not None or req.hole_diameter_mm is not None:
        geom.head_bearing_area = _math.pi / 4 * (
            geom.head_bearing_diameter ** 2 - geom.hole_diameter ** 2
        )
    mat = _build_material(req, geom.nominal_diameter)
    bolt = Bolt(
        geometry=geom, material=mat, grade=req.grade,
        thread_rolled=req.thread_rolled,
    )
    return BoltCircle(
        num_bolts=num_bolts,
        bolt_circle_diameter=pcd,
        bolt=bolt,
        nut_factor_K=req.nut_factor_K,
        assembly_torque=req.assembly_torque_Nmm,
        target_preload=req.target_preload_N,
        tightening_method=req.tightening_method,
        num_mating_surfaces=req.num_mating_surfaces,
        surface_roughness_Rz=req.surface_roughness_Rz,
        nut_factor_K_min=req.nut_factor_K_min,
        nut_factor_K_max=req.nut_factor_K_max,
        tool_scatter_pct=req.tool_scatter_pct,
        embedding_percent_of_max=req.embedding_percent_of_max,
    )


def _build_interface(
    layers_data: List[dict],
    interface_treatment: str,
    friction_coefficient: float,
    num_friction_interfaces: int,
    available_diameter: Optional[float] = None,
    cone_half_angle_deg: float = 30.0,
) -> ClampedInterface:
    layers = [
        ClampedLayer(
            material=l["material"],
            thickness=float(l["thickness_mm"]),
            youngs_modulus=float(l.get("E", FLANGE_MATERIAL_E.get(l["material"], 210000.0))),
            cte=float(l["cte"]) if l.get("cte") is not None else None,
        )
        for l in layers_data
    ]
    total = sum(l.thickness for l in layers)
    return ClampedInterface(
        total_clamped_length=total,
        layers=layers,
        interface_treatment=interface_treatment,
        friction_coefficient=friction_coefficient,
        num_friction_interfaces=num_friction_interfaces,
        available_diameter=available_diameter,
        cone_half_angle_deg=cone_half_angle_deg,
    )


def _build_load_cases(load_cases: List[LoadCaseRequest]) -> List[ExternalLoading]:
    return [
        ExternalLoading(
            axial_force=lc.axial_force_N,
            bending_moment=lc.bending_moment_Nmm,
            shear_force=lc.shear_force_N,
            torsion=lc.torsion_Nmm,
            axial_force_min=lc.axial_force_min_N,
            bending_moment_min=lc.bending_moment_min_Nmm,
            delta_T=lc.delta_T_C,
            load_plane=lc.load_plane,
            load_factor=lc.load_factor,
            case_name=lc.case_name,
        )
        for lc in load_cases
    ]


def _analysis_kwargs(req: AnalyzeRequest) -> dict:
    """Keyword arguments for run_vdi2230_analysis derived from the request."""
    return dict(
        load_intro_factor_n=req.load_intro_factor_n,
        plate_thickness=req.plate_thickness_mm,
        plate_yield_strength=req.plate_yield_strength_MPa,
        standard=req.standard,
        fos_yield=req.fos_yield,
        fos_ultimate=req.fos_ultimate,
        fos_separation=req.fos_separation,
        fos_slip=req.fos_slip,
        surface_pressure_limit=req.surface_pressure_limit_MPa,
        shear_plane_in_threads=req.shear_plane_in_threads,
        tapped_engagement_length=req.tapped_engagement_length_mm,
        tapped_material_uts=req.tapped_material_uts_MPa,
        fos_yield_installation=req.fos_yield_installation,
        fos_ultimate_installation=req.fos_ultimate_installation,
    )


def _build_all(req: AnalyzeRequest):
    bc = _build_bolt_circle(req, num_bolts=req.num_bolts, pcd=req.bolt_circle_diameter_mm)
    bc.pattern = req.pattern
    bc.rect_nx = req.rect_nx
    bc.rect_ny = req.rect_ny
    bc.rect_pitch_x = req.rect_pitch_x_mm
    bc.rect_pitch_y = req.rect_pitch_y_mm
    if req.custom_positions_mm:
        if len(req.custom_positions_mm) < 1:
            raise HTTPException(status_code=400, detail="custom_positions_mm is empty")
        bc.custom_positions = [(float(p[0]), float(p[1])) for p in req.custom_positions_mm]
    elif req.pattern == "custom":
        raise HTTPException(
            status_code=400,
            detail="pattern='custom' requires custom_positions_mm",
        )
    iface = _build_interface(
        req.layers, req.interface_treatment, req.friction_coefficient,
        req.num_friction_interfaces, req.available_flange_diameter_mm,
        req.cone_half_angle_deg,
    )
    iface.eccentricity_s = req.eccentricity_s_mm
    iface.load_eccentricity_a = req.load_eccentricity_a_mm
    load_cases = _build_load_cases(req.load_cases)
    return bc, iface, load_cases


def _run_analysis(req: AnalyzeRequest):
    bc, iface, load_cases = _build_all(req)
    results = run_vdi2230_analysis(
        bolt_circle=bc,
        interface=iface,
        load_cases=load_cases,
        **_analysis_kwargs(req),
    )
    return bc, iface, results


# ---------------------------------------------------------------------------
# Preview endpoints
# ---------------------------------------------------------------------------

@app.post("/api/preview/preload")
def preview_preload(req: PreloadPreviewRequest):
    """Calculate live preload preview for Page 1.

    If a layer stack is supplied, the embedding loss uses the correct
    joint compliance F_Z = f_Z/(δ_S+δ_P); otherwise a single steel layer
    of the grip length is assumed.
    """
    try:
        bc = _build_bolt_circle(req, num_bolts=1, pcd=0.0)

        layers_data = req.layers or [
            {"material": "Steel (carbon)", "thickness_mm": req.grip_length_mm, "E": 210000.0}
        ]
        iface = _build_interface(layers_data, "bare metal", 0.12, 1)
        stiff = calculate_joint_stiffness(bc, iface)

        result = calculate_preload(
            bc,
            iface.total_clamped_length,
            total_compliance=stiff.delta_S + stiff.delta_P,
            num_inner_interfaces=max(0, len(iface.layers) - 1),
        )
        geom = bc.bolt.geometry
        mat = bc.bolt.material
        sigma_proof = mat.proof_load_stress or mat.yield_strength
        util_pct = result.F_M_max / (geom.stress_area * sigma_proof) * 100 if sigma_proof > 0 else 0.0
        return {
            "F_M_nominal": result.F_M_nominal,
            "F_M_max": result.F_M_max,
            "F_M_min": result.F_M_min,
            "F_Z": result.F_Z,
            "F_preload_max": result.F_preload_max,
            "F_preload_min": result.F_preload_min,
            "alpha_A": result.alpha_A,
            "f_Z_displacement": result.f_Z_displacement,
            "proof_utilisation_pct": util_pct,
            "stress_area_mm2": geom.stress_area,
            "proof_load_stress_MPa": sigma_proof,
        }
    except HTTPException:
        raise
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/preview/stiffness")
def preview_stiffness(req: StiffnessPreviewRequest):
    """Calculate live stiffness preview for Page 2."""
    try:
        bc = _build_bolt_circle(req, num_bolts=req.num_bolts, pcd=req.bolt_circle_diameter_mm)
        iface = _build_interface(
            req.layers, req.interface_treatment, req.friction_coefficient,
            req.num_friction_interfaces, req.available_flange_diameter_mm,
            req.cone_half_angle_deg,
        )
        iface.eccentricity_s = req.eccentricity_s_mm
        iface.load_eccentricity_a = req.load_eccentricity_a_mm
        stiff = calculate_joint_stiffness(bc, iface, req.load_intro_factor_n)
        return {
            "delta_S": stiff.delta_S,
            "delta_P": stiff.delta_P,
            "phi_basic": stiff.phi_basic,
            "phi_n": stiff.phi_n,
            "load_intro_factor_n": stiff.load_intro_factor_n,
            "phi_concentric": stiff.phi_concentric,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

def _margin_to_dict(m) -> dict:
    return {
        "check_name": m.check_name,
        "value": m.value,
        "status": m.status,
        "binding": m.binding,
        "allowable": m.allowable,
        "applied": m.applied,
        "unit": m.unit,
        "explanation": m.explanation,
        "formula_latex": m.formula_latex,
    }


def _case_to_dict(case) -> dict:
    return {
        "case_name": case.case_name,
        "preload": {
            "F_M_nominal": case.preload.F_M_nominal,
            "F_M_max": case.preload.F_M_max,
            "F_M_min": case.preload.F_M_min,
            "F_Z": case.preload.F_Z,
            "F_preload_max": case.preload.F_preload_max,
            "F_preload_min": case.preload.F_preload_min,
            "alpha_A": case.preload.alpha_A,
            "f_Z_displacement": case.preload.f_Z_displacement,
        },
        "stiffness": {
            "delta_S": case.stiffness.delta_S,
            "delta_P": case.stiffness.delta_P,
            "phi_basic": case.stiffness.phi_basic,
            "phi_n": case.stiffness.phi_n,
            "load_intro_factor_n": case.stiffness.load_intro_factor_n,
            "phi_concentric": case.stiffness.phi_concentric,
        },
        "load_dist": {
            "critical_bolt_index": case.load_dist.critical_bolt_index,
            "F_axial_per_bolt": case.load_dist.F_axial_per_bolt,
            "F_bend_per_bolt": case.load_dist.F_bend_per_bolt,
            "V_shear_per_bolt": case.load_dist.V_shear_per_bolt,
            "V_direct_per_bolt": case.load_dist.V_direct_per_bolt,
            "V_torsion_per_bolt": case.load_dist.V_torsion_per_bolt,
            "F_total_axial": case.load_dist.F_total_axial,
            "F_total_axial_min": case.load_dist.F_total_axial_min,
            "bolt_angles_deg": case.load_dist.bolt_angles_deg,
            "bolt_axial_forces": case.load_dist.bolt_axial_forces,
            "bolt_positions": case.load_dist.bolt_positions,
        },
        "bolt_load_max": case.bolt_load_max,
        "bolt_load_amplitude": case.bolt_load_amplitude,
        "F_clamp_min": case.F_clamp_min,
        "F_thermal_delta": case.F_thermal_delta,
        "margins": [_margin_to_dict(m) for m in case.margins],
        "calc_steps": case.calc_steps,
        "warnings": case.warnings,
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    """Run full VDI 2230 analysis for all load cases."""
    try:
        _, _, results = _run_analysis(req)
        return {
            "standard": results.standard,
            "case_results": [_case_to_dict(c) for c in results.case_results],
        }
    except HTTPException:
        raise
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Sizing endpoints
# ---------------------------------------------------------------------------

class TorqueWindowRequest(AnalyzeRequest):
    torque_min_Nmm: Optional[float] = None
    torque_max_Nmm: Optional[float] = None
    sweep_points: int = 60


class SuggestBoltsRequest(AnalyzeRequest):
    sweep_points: int = 30
    max_candidates: int = 24


@app.post("/api/torque-window")
def torque_window_endpoint(req: TorqueWindowRequest):
    """Sweep the assembly torque and return the allowable band + recommendation."""
    try:
        bc, iface, load_cases = _build_all(req)
        return torque_window(
            bc, iface, load_cases,
            torque_min=req.torque_min_Nmm,
            torque_max=req.torque_max_Nmm,
            points=req.sweep_points,
            **_analysis_kwargs(req),
        )
    except HTTPException:
        raise
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/suggest-bolts")
def suggest_bolts_endpoint(req: SuggestBoltsRequest):
    """Evaluate library bolts of the same thread standard for this joint."""
    try:
        bc, iface, load_cases = _build_all(req)
        return {
            "candidates": suggest_bolts(
                bc, iface, load_cases,
                points=req.sweep_points,
                max_candidates=req.max_candidates,
                **_analysis_kwargs(req),
            )
        }
    except HTTPException:
        raise
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sensitivity")
def sensitivity_endpoint(req: AnalyzeRequest):
    """One-at-a-time sensitivity of the worst margin to key inputs."""
    try:
        bc, iface, load_cases = _build_all(req)
        return sensitivity(bc, iface, load_cases, **_analysis_kwargs(req))
    except HTTPException:
        raise
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------

@app.post("/api/export/json")
def export_json(req: AnalyzeRequest):
    """Return a JSON representation of the full case configuration."""
    payload = req.model_dump()
    json_bytes = json.dumps(payload, indent=2).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(json_bytes),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=boltsizer_case.json"},
    )


@app.post("/api/import/json")
async def import_json_endpoint(req: dict):
    """Accept a JSON dict and return it validated as an AnalyzeRequest."""
    try:
        parsed = AnalyzeRequest(**req)
        return parsed.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/export/pdf")
def export_pdf(req: AnalyzeRequest):
    """Run analysis and generate a PDF report."""
    try:
        _, _, results = _run_analysis(req)
        bolt_cfg = {
            "designation": req.designation,
            "grade": req.grade,
            "coating": "—",
            "nut_factor_K": req.nut_factor_K,
            "assembly_torque_Nmm": req.assembly_torque_Nmm,
            "tightening_method": req.tightening_method,
            "num_mating_surfaces": req.num_mating_surfaces,
            "surface_roughness_Rz": req.surface_roughness_Rz,
        }
        joint_cfg = {
            "num_bolts": req.num_bolts,
            "bolt_circle_diameter_mm": req.bolt_circle_diameter_mm,
            "layers": req.layers,
            "load_intro_factor_n": req.load_intro_factor_n,
            "friction_coefficient": req.friction_coefficient,
            "num_friction_interfaces": req.num_friction_interfaces,
            "plate_thickness_mm": req.plate_thickness_mm,
            "plate_yield_strength_MPa": req.plate_yield_strength_MPa,
        }
        meta = (req.report_meta or ReportMeta()).model_dump()
        from boltsizer.ecss.ecss_hb_32_23 import get_default_fos
        defaults = get_default_fos(req.standard)
        fos_summary = {
            "Yield (working)": req.fos_yield if req.fos_yield is not None else defaults["yield"],
            "Ultimate (working)": req.fos_ultimate if req.fos_ultimate is not None else defaults["ultimate"],
            "Separation": req.fos_separation if req.fos_separation is not None else defaults["separation"],
            "Slip": req.fos_slip if req.fos_slip is not None else defaults["slip"],
            "Installation yield": req.fos_yield_installation,
            "Installation ultimate": req.fos_ultimate_installation,
        }
        pdf_bytes = generate_pdf_report(
            results=results,
            bolt_cfg=bolt_cfg,
            joint_cfg=joint_cfg,
            report_meta=meta,
            fos_summary=fos_summary,
        )
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=boltsizer_report.pdf"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ProjectGroup(BaseModel):
    name: str
    request: AnalyzeRequest


class ProjectPdfRequest(BaseModel):
    groups: List[ProjectGroup]
    report_meta: Optional[ReportMeta] = None


@app.post("/api/export/project-pdf")
def export_project_pdf(req: ProjectPdfRequest):
    """Run every group's analysis and produce one combined project report."""
    try:
        if not req.groups:
            raise HTTPException(status_code=400, detail="No groups supplied")
        group_data = []
        for g in req.groups:
            _, _, results = _run_analysis(g.request)
            group_data.append({
                "name": g.name,
                "results": results,
                "bolt_cfg": {
                    "designation": g.request.designation,
                    "grade": g.request.grade,
                },
                "joint_cfg": {"num_bolts": g.request.num_bolts},
            })
        meta = (req.report_meta or ReportMeta()).model_dump()
        pdf_bytes = generate_project_pdf(group_data, meta)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=boltsizer_project.pdf"},
        )
    except HTTPException:
        raise
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

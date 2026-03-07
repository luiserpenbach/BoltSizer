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
from boltsizer.models.bolt import Bolt
from boltsizer.models.joint import BoltCircle, ClampedInterface, ClampedLayer, ExternalLoading
from boltsizer.calculations.preload import calculate_preload
from boltsizer.calculations.joint_stiffness import calculate_joint_stiffness
from boltsizer.calculations.vdi2230 import run_vdi2230_analysis
from boltsizer.export.pdf_report import generate_pdf_report

app = FastAPI(title="BoltSizer API", version="1.0.0")

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

class PreloadPreviewRequest(BaseModel):
    designation: str
    grade: str
    shank_length_mm: float = 20.0
    threaded_length_mm: float = 15.0
    nut_factor_K: float = 0.16
    assembly_torque_Nmm: float = 0.0
    target_preload_N: float = 0.0
    tightening_method: str = "torque_wrench"
    num_mating_surfaces: int = 2
    surface_roughness_Rz: float = 6.3
    grip_length_mm: float = 40.0


class StiffnessPreviewRequest(BaseModel):
    # Bolt
    designation: str
    grade: str
    shank_length_mm: float = 20.0
    threaded_length_mm: float = 15.0
    nut_factor_K: float = 0.16
    assembly_torque_Nmm: float = 0.0
    target_preload_N: float = 0.0
    tightening_method: str = "torque_wrench"
    num_mating_surfaces: int = 2
    surface_roughness_Rz: float = 6.3
    # Joint
    num_bolts: int = 8
    bolt_circle_diameter_mm: float = 100.0
    layers: List[dict] = Field(default_factory=lambda: [{"material": "Steel (carbon)", "thickness_mm": 20.0, "E": 210000.0}])
    interface_treatment: str = "bare metal"
    friction_coefficient: float = 0.12
    num_friction_interfaces: int = 1
    load_intro_factor_n: float = 0.5


class LoadCaseRequest(BaseModel):
    case_name: str = "LC1"
    axial_force_N: float = 0.0
    bending_moment_Nmm: float = 0.0
    shear_force_N: float = 0.0
    torsion_Nmm: float = 0.0
    load_factor: float = 1.0


class AnalyzeRequest(BaseModel):
    # Bolt selection
    designation: str
    grade: str
    shank_length_mm: float = 20.0
    threaded_length_mm: float = 15.0
    nut_factor_K: float = 0.16
    assembly_torque_Nmm: float = 0.0
    target_preload_N: float = 0.0
    tightening_method: str = "torque_wrench"
    num_mating_surfaces: int = 2
    surface_roughness_Rz: float = 6.3
    # Joint geometry
    num_bolts: int = 8
    bolt_circle_diameter_mm: float = 100.0
    layers: List[dict] = Field(default_factory=lambda: [{"material": "Steel (carbon)", "thickness_mm": 20.0, "E": 210000.0}])
    interface_treatment: str = "bare metal"
    friction_coefficient: float = 0.12
    num_friction_interfaces: int = 1
    load_intro_factor_n: float = 0.5
    plate_thickness_mm: float = 20.0
    plate_yield_strength_MPa: float = 240.0
    # Load cases
    load_cases: List[LoadCaseRequest] = Field(default_factory=lambda: [LoadCaseRequest()])
    standard: Literal["VDI", "ECSS"] = "VDI"


# ---------------------------------------------------------------------------
# Helper: build Python objects from request dicts
# ---------------------------------------------------------------------------

def _build_bolt_circle(req: AnalyzeRequest | StiffnessPreviewRequest | PreloadPreviewRequest, num_bolts: int = 1, pcd: float = 0.0) -> BoltCircle:
    geom = get_bolt_geometry(req.designation, req.shank_length_mm, req.threaded_length_mm)
    mat = get_material(req.grade) if req.grade != "Custom" else get_material("ISO 8.8")
    bolt = Bolt(geometry=geom, material=mat, grade=req.grade)
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
    )


def _build_interface(layers_data: List[dict], interface_treatment: str, friction_coefficient: float, num_friction_interfaces: int) -> ClampedInterface:
    layers = [
        ClampedLayer(
            material=l["material"],
            thickness=float(l["thickness_mm"]),
            youngs_modulus=float(l.get("E", FLANGE_MATERIAL_E.get(l["material"], 210000.0))),
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
    )


# ---------------------------------------------------------------------------
# Preview endpoints
# ---------------------------------------------------------------------------

@app.post("/api/preview/preload")
def preview_preload(req: PreloadPreviewRequest):
    """Calculate live preload preview for Page 1."""
    try:
        bc = _build_bolt_circle(req, num_bolts=1, pcd=0.0)
        result = calculate_preload(bc, req.grip_length_mm)
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
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/preview/stiffness")
def preview_stiffness(req: StiffnessPreviewRequest):
    """Calculate live stiffness preview for Page 2."""
    try:
        bc = _build_bolt_circle(req, num_bolts=req.num_bolts, pcd=req.bolt_circle_diameter_mm)
        iface = _build_interface(req.layers, req.interface_treatment, req.friction_coefficient, req.num_friction_interfaces)
        stiff = calculate_joint_stiffness(bc, iface, req.load_intro_factor_n)
        return {
            "delta_S": stiff.delta_S,
            "delta_P": stiff.delta_P,
            "phi_basic": stiff.phi_basic,
            "phi_n": stiff.phi_n,
            "load_intro_factor_n": stiff.load_intro_factor_n,
        }
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
        },
        "load_dist": {
            "critical_bolt_index": case.load_dist.critical_bolt_index,
            "F_axial_per_bolt": case.load_dist.F_axial_per_bolt,
            "F_bend_per_bolt": case.load_dist.F_bend_per_bolt,
            "V_shear_per_bolt": case.load_dist.V_shear_per_bolt,
            "F_total_axial": case.load_dist.F_total_axial,
            "bolt_angles_deg": case.load_dist.bolt_angles_deg,
            "bolt_axial_forces": case.load_dist.bolt_axial_forces,
        },
        "bolt_load_max": case.bolt_load_max,
        "bolt_load_amplitude": case.bolt_load_amplitude,
        "F_clamp_min": case.F_clamp_min,
        "margins": [_margin_to_dict(m) for m in case.margins],
        "calc_steps": case.calc_steps,
        "warnings": case.warnings,
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    """Run full VDI 2230 analysis for all load cases."""
    try:
        bc = _build_bolt_circle(req, num_bolts=req.num_bolts, pcd=req.bolt_circle_diameter_mm)
        iface = _build_interface(req.layers, req.interface_treatment, req.friction_coefficient, req.num_friction_interfaces)
        load_cases = [
            ExternalLoading(
                axial_force=lc.axial_force_N,
                bending_moment=lc.bending_moment_Nmm,
                shear_force=lc.shear_force_N,
                torsion=lc.torsion_Nmm,
                load_factor=lc.load_factor,
                case_name=lc.case_name,
            )
            for lc in req.load_cases
        ]
        results = run_vdi2230_analysis(
            bolt_circle=bc,
            interface=iface,
            load_cases=load_cases,
            load_intro_factor_n=req.load_intro_factor_n,
            plate_thickness=req.plate_thickness_mm,
            plate_yield_strength=req.plate_yield_strength_MPa,
            standard=req.standard,
        )
        return {
            "standard": results.standard,
            "case_results": [_case_to_dict(c) for c in results.case_results],
        }
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
        bc = _build_bolt_circle(req, num_bolts=req.num_bolts, pcd=req.bolt_circle_diameter_mm)
        iface = _build_interface(req.layers, req.interface_treatment, req.friction_coefficient, req.num_friction_interfaces)
        load_cases = [
            ExternalLoading(
                axial_force=lc.axial_force_N,
                bending_moment=lc.bending_moment_Nmm,
                shear_force=lc.shear_force_N,
                torsion=lc.torsion_Nmm,
                load_factor=lc.load_factor,
                case_name=lc.case_name,
            )
            for lc in req.load_cases
        ]
        results = run_vdi2230_analysis(
            bolt_circle=bc,
            interface=iface,
            load_cases=load_cases,
            load_intro_factor_n=req.load_intro_factor_n,
            plate_thickness=req.plate_thickness_mm,
            plate_yield_strength=req.plate_yield_strength_MPa,
            standard=req.standard,
        )
        pdf_bytes = generate_pdf_report(bc, iface, results)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=boltsizer_report.pdf"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

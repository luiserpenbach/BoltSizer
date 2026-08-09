import axios from "axios";
import type {
  BoltLibraryEntry,
  MaterialEntry,
  CoatingEntry,
  TighteningMethod,
  PreloadPreview,
  StiffnessPreview,
  AnalysisResults,
  BoltConfig,
  JointConfig,
  LoadCase,
} from "../types";

const api = axios.create({ baseURL: "" });

// ---- Reference data ----

export const fetchBolts = () =>
  api.get<Record<string, BoltLibraryEntry>>("/api/bolts").then((r) => r.data);

export const fetchMaterials = () =>
  api.get<Record<string, MaterialEntry>>("/api/materials").then((r) => r.data);

export const fetchCoatings = () =>
  api.get<Record<string, CoatingEntry>>("/api/coatings").then((r) => r.data);

export const fetchTighteningMethods = () =>
  api
    .get<Record<string, TighteningMethod>>("/api/tightening-methods")
    .then((r) => r.data);

export const fetchFlangeMaterials = () =>
  api.get<Record<string, number>>("/api/flange-materials").then((r) => r.data);

// ---- Previews ----

export interface PreloadPreviewReq {
  designation: string;
  grade: string;
  shank_length_mm: number;
  threaded_length_mm: number;
  nut_factor_K: number;
  assembly_torque_Nmm: number;
  target_preload_N: number;
  tightening_method: string;
  num_mating_surfaces: number;
  surface_roughness_Rz: number;
  grip_length_mm: number;
  layers?: { material: string; thickness_mm: number; E: number }[];
}

export const previewPreload = (req: PreloadPreviewReq) =>
  api.post<PreloadPreview>("/api/preview/preload", req).then((r) => r.data);

export interface StiffnessPreviewReq {
  designation: string;
  grade: string;
  shank_length_mm: number;
  threaded_length_mm: number;
  nut_factor_K: number;
  assembly_torque_Nmm: number;
  target_preload_N: number;
  tightening_method: string;
  num_mating_surfaces: number;
  surface_roughness_Rz: number;
  num_bolts: number;
  bolt_circle_diameter_mm: number;
  layers: { material: string; thickness_mm: number; E: number }[];
  interface_treatment: string;
  friction_coefficient: number;
  num_friction_interfaces: number;
  load_intro_factor_n: number;
}

export const previewStiffness = (req: StiffnessPreviewReq) =>
  api
    .post<StiffnessPreview>("/api/preview/stiffness", req)
    .then((r) => r.data);

// ---- Analysis ----

export interface AnalyzeReq {
  designation: string;
  grade: string;
  shank_length_mm: number;
  threaded_length_mm: number;
  nut_factor_K: number;
  assembly_torque_Nmm: number;
  target_preload_N: number;
  tightening_method: string;
  num_mating_surfaces: number;
  surface_roughness_Rz: number;
  num_bolts: number;
  bolt_circle_diameter_mm: number;
  layers: { material: string; thickness_mm: number; E: number }[];
  interface_treatment: string;
  friction_coefficient: number;
  num_friction_interfaces: number;
  load_intro_factor_n: number;
  plate_thickness_mm: number;
  plate_yield_strength_MPa: number;
  load_cases: LoadCase[];
  standard: "VDI" | "ECSS";
}

export function buildAnalyzeReq(
  bolt: BoltConfig,
  joint: JointConfig,
  loadCases: LoadCase[],
  standard: "VDI" | "ECSS" = "VDI"
): AnalyzeReq {
  return {
    designation: bolt.designation,
    grade: bolt.grade,
    shank_length_mm: bolt.shank_length_mm,
    threaded_length_mm: bolt.threaded_length_mm,
    nut_factor_K: bolt.nut_factor_K,
    assembly_torque_Nmm: bolt.use_target_preload ? 0 : bolt.assembly_torque_Nmm,
    target_preload_N: bolt.use_target_preload ? bolt.target_preload_N : 0,
    tightening_method: bolt.tightening_method,
    num_mating_surfaces: bolt.num_mating_surfaces,
    surface_roughness_Rz: bolt.surface_roughness_Rz,
    num_bolts: joint.num_bolts,
    bolt_circle_diameter_mm: joint.bolt_circle_diameter_mm,
    layers: joint.layers,
    interface_treatment: joint.interface_treatment,
    friction_coefficient: joint.friction_coefficient,
    num_friction_interfaces: joint.num_friction_interfaces,
    load_intro_factor_n: joint.load_intro_factor_n,
    plate_thickness_mm: joint.plate_thickness_mm,
    plate_yield_strength_MPa: joint.plate_yield_strength_MPa,
    load_cases: loadCases,
    standard,
  };
}

export const runAnalysis = (req: AnalyzeReq) =>
  api.post<AnalysisResults>("/api/analyze", req).then((r) => r.data);

// ---- Export ----

export const exportJson = async (req: AnalyzeReq) => {
  const resp = await api.post("/api/export/json", req, { responseType: "blob" });
  const url = URL.createObjectURL(resp.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = "boltsizer_case.json";
  a.click();
  URL.revokeObjectURL(url);
};

export const exportPdf = async (req: AnalyzeReq) => {
  const resp = await api.post("/api/export/pdf", req, { responseType: "blob" });
  const url = URL.createObjectURL(resp.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = "boltsizer_report.pdf";
  a.click();
  URL.revokeObjectURL(url);
};

export const importJson = (data: object) =>
  api.post<AnalyzeReq>("/api/import/json", data).then((r) => r.data);

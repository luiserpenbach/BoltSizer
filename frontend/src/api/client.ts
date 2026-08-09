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
  FosConfig,
  ReportMeta,
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
  nut_factor_K_min?: number | null;
  nut_factor_K_max?: number | null;
  tool_scatter_pct?: number | null;
  assembly_torque_Nmm: number;
  target_preload_N: number;
  tightening_method: string;
  num_mating_surfaces: number;
  surface_roughness_Rz: number;
  grip_length_mm: number;
  layers?: { material: string; thickness_mm: number; E: number }[];
  head_bearing_diameter_mm?: number | null;
  hole_diameter_mm?: number | null;
  thread_rolled?: "before_ht" | "after_ht";
  embedding_percent_of_max?: number | null;
  custom_material?: AnalyzeReq["custom_material"];
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
  available_flange_diameter_mm?: number | null;
  head_bearing_diameter_mm?: number | null;
  hole_diameter_mm?: number | null;
  eccentricity_s_mm?: number;
  load_eccentricity_a_mm?: number;
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
  nut_factor_K_min?: number | null;
  nut_factor_K_max?: number | null;
  tool_scatter_pct?: number | null;
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
  fos_yield?: number | null;
  fos_ultimate?: number | null;
  fos_separation?: number | null;
  fos_slip?: number | null;
  fos_yield_installation?: number;
  fos_ultimate_installation?: number;
  head_bearing_diameter_mm?: number | null;
  hole_diameter_mm?: number | null;
  thread_rolled?: "before_ht" | "after_ht";
  embedding_percent_of_max?: number | null;
  custom_material?: {
    yield_strength_MPa: number;
    uts_MPa: number;
    youngs_modulus_MPa: number;
    proof_load_stress_MPa?: number | null;
    fatigue_limit_MPa?: number | null;
    cte_per_K?: number | null;
  } | null;
  available_flange_diameter_mm?: number | null;
  tapped_engagement_length_mm?: number | null;
  tapped_material_uts_MPa?: number | null;
  pattern?: "circle" | "rectangle" | "custom";
  rect_nx?: number;
  rect_ny?: number;
  rect_pitch_x_mm?: number;
  rect_pitch_y_mm?: number;
  custom_positions_mm?: [number, number][] | null;
  eccentricity_s_mm?: number;
  load_eccentricity_a_mm?: number;
  load_cases: LoadCase[];
  standard: "VDI" | "ECSS";
  report_meta?: ReportMeta | null;
}

/** Parse the custom-positions textarea: one "x,y" pair [mm] per line. */
export function parseCustomPositions(text: string): [number, number][] {
  return text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0)
    .map((l) => {
      const parts = l.split(/[,;\s]+/).map(parseFloat);
      if (parts.length < 2 || parts.some(Number.isNaN)) {
        throw new Error(`Invalid position line: "${l}" (expected "x,y")`);
      }
      return [parts[0], parts[1]] as [number, number];
    });
}

/** DIN 912 socket-head bearing OD (≈ head diameter d_k) per metric size. */
const DIN912_DW: Record<string, number> = {
  M3: 5.5, M4: 7.0, M5: 8.5, M6: 10.0, M8: 13.0, M10: 16.0, M12: 18.0,
  M14: 21.0, M16: 24.0, M18: 27.0, M20: 30.0, M22: 33.0, M24: 36.0,
  M27: 40.0, M30: 45.0, M36: 54.0,
};

export function resolveHeadBearingDiameter(bolt: BoltConfig): number | null {
  if (bolt.head_style === "custom") return bolt.head_bearing_diameter_mm;
  if (bolt.head_style === "din912") {
    const base = bolt.designation.split("x")[0];
    return DIN912_DW[base] ?? null;
  }
  return null; // hex → library default (ISO 4014)
}

export function buildAnalyzeReq(
  bolt: BoltConfig,
  joint: JointConfig,
  loadCases: LoadCase[],
  standard: "VDI" | "ECSS" = "VDI",
  fos?: FosConfig,
  reportMeta?: ReportMeta
): AnalyzeReq {
  const useRange = bolt.use_friction_range && bolt.nut_factor_K_min != null;
  return {
    designation: bolt.designation,
    grade: bolt.grade,
    shank_length_mm: bolt.shank_length_mm,
    threaded_length_mm: bolt.threaded_length_mm,
    nut_factor_K: bolt.nut_factor_K,
    nut_factor_K_min: useRange ? bolt.nut_factor_K_min : null,
    nut_factor_K_max: useRange ? bolt.nut_factor_K_max : null,
    tool_scatter_pct: useRange ? bolt.tool_scatter_pct / 100 : null,
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
    fos_yield: fos?.fos_yield ?? null,
    fos_ultimate: fos?.fos_ultimate ?? null,
    fos_separation: fos?.fos_separation ?? null,
    fos_slip: fos?.fos_slip ?? null,
    fos_yield_installation: fos?.fos_yield_installation ?? 1.0,
    fos_ultimate_installation: fos?.fos_ultimate_installation ?? 1.0,
    head_bearing_diameter_mm: resolveHeadBearingDiameter(bolt),
    hole_diameter_mm: bolt.hole_diameter_mm,
    thread_rolled: bolt.thread_rolled,
    embedding_percent_of_max:
      bolt.embedding_mode === "percent" ? bolt.embedding_percent / 100 : null,
    custom_material: bolt.grade === "Custom" ? bolt.custom_material : null,
    available_flange_diameter_mm: joint.available_flange_diameter_mm,
    tapped_engagement_length_mm:
      joint.joint_type === "tapped" ? joint.tapped_engagement_length_mm : null,
    tapped_material_uts_MPa:
      joint.joint_type === "tapped" ? joint.tapped_material_uts_MPa : null,
    pattern: joint.pattern,
    rect_nx: joint.rect_nx,
    rect_ny: joint.rect_ny,
    rect_pitch_x_mm: joint.rect_pitch_x_mm,
    rect_pitch_y_mm: joint.rect_pitch_y_mm,
    custom_positions_mm:
      joint.pattern === "custom" && joint.custom_positions_text.trim()
        ? parseCustomPositions(joint.custom_positions_text)
        : null,
    eccentricity_s_mm: joint.eccentricity_s_mm,
    load_eccentricity_a_mm: joint.load_eccentricity_a_mm,
    load_cases: loadCases,
    standard,
    report_meta: reportMeta ?? null,
  };
}

// ---- Sensitivity ----

export interface SensitivityParam {
  name: string;
  low_ms: number;
  high_ms: number;
}

export interface SensitivityResult {
  baseline_ms: number;
  params: SensitivityParam[];
}

export const fetchSensitivity = (req: AnalyzeReq) =>
  api.post<SensitivityResult>("/api/sensitivity", req).then((r) => r.data);

// ---- Project (multi-group) ----

export const exportProjectPdf = async (
  groups: { name: string; request: AnalyzeReq }[],
  reportMeta?: ReportMeta
) => {
  const resp = await api.post(
    "/api/export/project-pdf",
    { groups, report_meta: reportMeta ?? null },
    { responseType: "blob" }
  );
  const url = URL.createObjectURL(resp.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = "boltsizer_project.pdf";
  a.click();
  URL.revokeObjectURL(url);
};

export const runAnalysis = (req: AnalyzeReq) =>
  api.post<AnalysisResults>("/api/analyze", req).then((r) => r.data);

// ---- Sizing ----

export interface TorqueWindowPoint {
  torque: number;
  min_ms: number;
  governing: string;
  margins: Record<string, number>;
}

export interface TorqueWindowResult {
  points: TorqueWindowPoint[];
  window: { t_lo: number; t_hi: number } | null;
  recommended: { torque: number; min_ms: number; governing: string } | null;
}

export const fetchTorqueWindow = (req: AnalyzeReq, sweepPoints = 60) =>
  api
    .post<TorqueWindowResult>("/api/torque-window", { ...req, sweep_points: sweepPoints })
    .then((r) => r.data);

export interface BoltCandidate {
  designation: string;
  d: number;
  A_s: number;
  passes: boolean;
  window: { t_lo: number; t_hi: number } | null;
  recommended: { torque: number; min_ms: number; governing: string } | null;
  best_min_ms: number | null;
  governing: string;
}

export const fetchSuggestBolts = (req: AnalyzeReq) =>
  api
    .post<{ candidates: BoltCandidate[] }>("/api/suggest-bolts", req)
    .then((r) => r.data.candidates);

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

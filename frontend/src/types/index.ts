// TypeScript types mirroring Python boltsizer dataclasses and API schemas

export interface BoltLibraryEntry {
  standard: string;
  designation: string;
  nominal_diameter: number;
  pitch: number;
  stress_area: number;
  head_bearing_area: number;
  minor_diameter: number;
  pitch_diameter: number;
}

export interface MaterialEntry {
  name: string;
  yield_strength: number;
  uts: number;
  youngs_modulus: number;
  fatigue_limit: number | null;
  proof_load_stress: number;
  source: string;
}

export interface CoatingEntry {
  k_nom: number;
  k_min: number;
  k_max: number;
  description: string;
}

export interface TighteningMethod {
  alpha_A: number;
  description: string;
  label: string;
}

// ---- Layer / Joint ----

export interface LayerConfig {
  material: string;
  thickness_mm: number;
  E: number;
}

// ---- Store state config structs ----

export type HeadStyle = "hex" | "din912" | "custom";
export type ThreadRolled = "before_ht" | "after_ht";
export type EmbeddingMode = "vdi" | "percent";

export interface CustomMaterialConfig {
  yield_strength_MPa: number;
  uts_MPa: number;
  youngs_modulus_MPa: number;
  proof_load_stress_MPa: number | null;
  fatigue_limit_MPa: number | null;
  cte_per_K: number | null;
}

export interface BoltConfig {
  designation: string;
  grade: string;
  shank_length_mm: number;
  threaded_length_mm: number;
  nut_factor_K: number;
  nut_factor_K_min: number | null;
  nut_factor_K_max: number | null;
  use_friction_range: boolean;
  tool_scatter_pct: number; // percent, e.g. 5 = ±5%
  assembly_torque_Nmm: number;
  target_preload_N: number;
  use_target_preload: boolean;
  tightening_method: string;
  num_mating_surfaces: number;
  surface_roughness_Rz: number;
  coating: string;
  // Advanced
  head_style: HeadStyle;
  head_bearing_diameter_mm: number | null; // used when head_style = custom
  hole_diameter_mm: number | null;         // null = library default
  thread_rolled: ThreadRolled;
  embedding_mode: EmbeddingMode;
  embedding_percent: number;               // % of F_M_max, when mode = percent
  custom_material: CustomMaterialConfig | null;
}

/** Factors of safety; null = use the selected standard's default. */
export interface FosConfig {
  fos_yield: number | null;
  fos_ultimate: number | null;
  fos_separation: number | null;
  fos_slip: number | null;
  fos_yield_installation: number;
  fos_ultimate_installation: number;
}

export interface ReportMeta {
  project_name: string;
  revision: string;
  engineer_name: string;
}

export interface JointConfig {
  num_bolts: number;
  bolt_circle_diameter_mm: number;
  layers: LayerConfig[];
  interface_treatment: string;
  friction_coefficient: number;
  num_friction_interfaces: number;
  load_intro_factor_n: number;
  plate_thickness_mm: number;
  plate_yield_strength_MPa: number;
  // Advanced
  joint_type: "through" | "tapped";
  tapped_engagement_length_mm: number;
  tapped_material_uts_MPa: number;
  available_flange_diameter_mm: number | null; // null = unlimited cone
  auto_bearing: boolean; // derive bearing plate inputs from the stack
  // Pattern (Wave 4)
  pattern: "circle" | "rectangle" | "custom";
  rect_nx: number;
  rect_ny: number;
  rect_pitch_x_mm: number;
  rect_pitch_y_mm: number;
  custom_positions_text: string; // "x,y" per line [mm]
  // Eccentric clamping / loading (VDI §5.3.2)
  eccentricity_s_mm: number;
  load_eccentricity_a_mm: number;
}

export interface LoadCase {
  case_name: string;
  axial_force_N: number;
  bending_moment_Nmm: number;
  shear_force_N: number;
  torsion_Nmm: number;
  load_factor: number;
  axial_force_min_N: number;
  bending_moment_min_Nmm: number;
  delta_T_C: number;
  load_plane: "interface" | "bolt_head";
}

// ---- API Results ----

export interface PreloadPreview {
  F_M_nominal: number;
  F_M_max: number;
  F_M_min: number;
  F_Z: number;
  F_preload_max: number;
  F_preload_min: number;
  alpha_A: number;
  f_Z_displacement: number;
  proof_utilisation_pct: number;
  stress_area_mm2: number;
  proof_load_stress_MPa: number;
}

export interface StiffnessPreview {
  delta_S: number;
  delta_P: number;
  phi_basic: number;
  phi_n: number;
  load_intro_factor_n: number;
}

export type MarginStatus = "PASS" | "FAIL" | "WARNING";

export interface MarginOfSafety {
  check_name: string;
  value: number;
  status: MarginStatus;
  binding: boolean;
  allowable: number;
  applied: number;
  unit: string;
  explanation: string;
  formula_latex: string;
}

export interface CalcStep {
  step: string;
  formula_latex: string;
  substitution: string;
  result: string;
  explanation: string;
}

export interface PreloadResult {
  F_M_nominal: number;
  F_M_max: number;
  F_M_min: number;
  F_Z: number;
  F_preload_max: number;
  F_preload_min: number;
  alpha_A: number;
  f_Z_displacement: number;
}

export interface StiffnessResult {
  delta_S: number;
  delta_P: number;
  phi_basic: number;
  phi_n: number;
  load_intro_factor_n: number;
}

export interface LoadDistResult {
  critical_bolt_index: number;
  F_axial_per_bolt: number;
  F_bend_per_bolt: number;
  V_shear_per_bolt: number;
  V_direct_per_bolt?: number;
  V_torsion_per_bolt?: number;
  F_total_axial: number;
  F_total_axial_min?: number;
  bolt_angles_deg: number[];
  bolt_axial_forces: number[];
  bolt_positions?: [number, number][];
}

export interface BoltResults {
  case_name: string;
  preload: PreloadResult;
  stiffness: StiffnessResult;
  load_dist: LoadDistResult;
  bolt_load_max: number;
  bolt_load_amplitude: number;
  F_clamp_min: number;
  margins: MarginOfSafety[];
  calc_steps: CalcStep[];
  warnings: string[];
}

export interface AnalysisResults {
  standard: "VDI" | "ECSS";
  case_results: BoltResults[];
}

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  BoltConfig,
  JointConfig,
  LoadCase,
  AnalysisResults,
  FosConfig,
  ReportMeta,
} from "../types";
import { runAnalysis, buildAnalyzeReq } from "../api/client";

export interface GroupSnapshot {
  boltConfig: BoltConfig;
  jointConfig: JointConfig;
  loadCases: LoadCase[];
  standard: "VDI" | "ECSS";
  fos: FosConfig;
}

export interface AppState {
  currentStep: number;
  boltConfig: BoltConfig;
  jointConfig: JointConfig;
  loadCases: LoadCase[];
  fos: FosConfig;
  reportMeta: ReportMeta;
  /** Named bolt-group snapshots for multi-group projects. */
  groups: Record<string, GroupSnapshot>;
  results: AnalysisResults | null;
  /** Serialized request behind the currently displayed results (staleness). */
  lastRunKey: string | null;
  isAnalyzing: boolean;
  analyzeError: string | null;
  standard: "VDI" | "ECSS";

  setCurrentStep: (step: number) => void;
  setBoltConfig: (cfg: Partial<BoltConfig>) => void;
  setJointConfig: (cfg: Partial<JointConfig>) => void;
  setLoadCases: (lcs: LoadCase[]) => void;
  addLoadCase: () => void;
  removeLoadCase: (index: number) => void;
  updateLoadCase: (index: number, lc: Partial<LoadCase>) => void;
  setStandard: (s: "VDI" | "ECSS") => void;
  setFos: (f: Partial<FosConfig>) => void;
  setReportMeta: (m: Partial<ReportMeta>) => void;
  saveGroup: (name: string) => void;
  loadGroup: (name: string) => void;
  deleteGroup: (name: string) => void;
  runAnalysis: () => Promise<void>;
  clearResults: () => void;
  resetAll: () => void;
  importConfig: (cfg: Partial<AppState>) => void;
}

const DEFAULT_BOLT: BoltConfig = {
  designation: "M12",
  grade: "ISO 10.9",
  shank_length_mm: 20,
  threaded_length_mm: 15,
  nut_factor_K: 0.16,
  nut_factor_K_min: 0.14,
  nut_factor_K_max: 0.18,
  use_friction_range: true,
  tool_scatter_pct: 5,
  assembly_torque_Nmm: 85000,
  target_preload_N: 30000,
  use_target_preload: false,
  tightening_method: "torque_wrench",
  num_mating_surfaces: 2,
  surface_roughness_Rz: 6.3,
  coating: "Cadmium plated",
  head_style: "hex",
  head_bearing_diameter_mm: null,
  hole_diameter_mm: null,
  thread_rolled: "before_ht",
  embedding_mode: "vdi",
  embedding_percent: 5,
  custom_material: null,
};

const DEFAULT_JOINT: JointConfig = {
  num_bolts: 8,
  bolt_circle_diameter_mm: 100,
  layers: [{ material: "Steel (carbon)", thickness_mm: 20, E: 210000 }],
  interface_treatment: "bare metal",
  friction_coefficient: 0.12,
  num_friction_interfaces: 1,
  load_intro_factor_n: 0.5,
  plate_thickness_mm: 20,
  plate_yield_strength_MPa: 240,
  joint_type: "through",
  tapped_engagement_length_mm: 12,
  tapped_material_uts_MPa: 310,
  available_flange_diameter_mm: null,
  auto_bearing: true,
  pattern: "circle",
  rect_nx: 2,
  rect_ny: 2,
  rect_pitch_x_mm: 60,
  rect_pitch_y_mm: 60,
  custom_positions_text: "",
  eccentricity_s_mm: 0,
  load_eccentricity_a_mm: 0,
};

const DEFAULT_LOAD_CASE: LoadCase = {
  case_name: "LC1",
  axial_force_N: 10000,
  bending_moment_Nmm: 0,
  shear_force_N: 5000,
  torsion_Nmm: 0,
  load_factor: 1.5,
  axial_force_min_N: 0,
  bending_moment_min_Nmm: 0,
  delta_T_C: 0,
  load_plane: "interface",
};

export { DEFAULT_LOAD_CASE };

const DEFAULT_FOS: FosConfig = {
  fos_yield: null,
  fos_ultimate: null,
  fos_separation: null,
  fos_slip: null,
  fos_yield_installation: 1.0,
  fos_ultimate_installation: 1.0,
};

const DEFAULT_META: ReportMeta = {
  project_name: "",
  revision: "A",
  engineer_name: "",
};

/** Build the request key used for staleness detection. */
export function requestKey(s: {
  boltConfig: BoltConfig;
  jointConfig: JointConfig;
  loadCases: LoadCase[];
  standard: "VDI" | "ECSS";
  fos: FosConfig;
}): string {
  return JSON.stringify(
    buildAnalyzeReq(s.boltConfig, s.jointConfig, s.loadCases, s.standard, s.fos)
  );
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      currentStep: 0,
      boltConfig: DEFAULT_BOLT,
      jointConfig: DEFAULT_JOINT,
      loadCases: [{ ...DEFAULT_LOAD_CASE }],
      fos: { ...DEFAULT_FOS },
      reportMeta: { ...DEFAULT_META },
      groups: {},
      results: null,
      lastRunKey: null,
      isAnalyzing: false,
      analyzeError: null,
      standard: "VDI",

      setCurrentStep: (step) => set({ currentStep: step }),

      setBoltConfig: (cfg) =>
        set((s) => ({ boltConfig: { ...s.boltConfig, ...cfg } })),

      setJointConfig: (cfg) =>
        set((s) => ({ jointConfig: { ...s.jointConfig, ...cfg } })),

      setLoadCases: (lcs) => set({ loadCases: lcs }),

      addLoadCase: () =>
        set((s) => ({
          loadCases: [
            ...s.loadCases,
            { ...DEFAULT_LOAD_CASE, case_name: `LC${s.loadCases.length + 1}` },
          ],
        })),

      removeLoadCase: (index) =>
        set((s) => ({
          loadCases: s.loadCases.filter((_, i) => i !== index),
        })),

      updateLoadCase: (index, lc) =>
        set((s) => ({
          loadCases: s.loadCases.map((c, i) => (i === index ? { ...c, ...lc } : c)),
        })),

      setStandard: (standard) => set({ standard }),

      setFos: (f) => set((s) => ({ fos: { ...s.fos, ...f } })),

      setReportMeta: (m) => set((s) => ({ reportMeta: { ...s.reportMeta, ...m } })),

      saveGroup: (name) =>
        set((s) => ({
          groups: {
            ...s.groups,
            [name]: {
              boltConfig: JSON.parse(JSON.stringify(s.boltConfig)),
              jointConfig: JSON.parse(JSON.stringify(s.jointConfig)),
              loadCases: JSON.parse(JSON.stringify(s.loadCases)),
              standard: s.standard,
              fos: { ...s.fos },
            },
          },
        })),

      loadGroup: (name) =>
        set((s) => {
          const g = s.groups[name];
          if (!g) return s;
          return {
            ...s,
            boltConfig: JSON.parse(JSON.stringify(g.boltConfig)),
            jointConfig: JSON.parse(JSON.stringify(g.jointConfig)),
            loadCases: JSON.parse(JSON.stringify(g.loadCases)),
            standard: g.standard,
            fos: { ...g.fos },
            results: null,
            lastRunKey: null,
          };
        }),

      deleteGroup: (name) =>
        set((s) => {
          const groups = { ...s.groups };
          delete groups[name];
          return { groups };
        }),

      runAnalysis: async () => {
        const { boltConfig, jointConfig, loadCases, standard, fos, reportMeta } = get();
        set({ isAnalyzing: true, analyzeError: null });
        try {
          const req = buildAnalyzeReq(boltConfig, jointConfig, loadCases, standard, fos, reportMeta);
          const results = await runAnalysis(req);
          set({
            results,
            isAnalyzing: false,
            lastRunKey: requestKey({ boltConfig, jointConfig, loadCases, standard, fos }),
          });
        } catch (e: unknown) {
          const msg =
            e instanceof Error ? e.message : "Analysis failed — check inputs";
          set({ analyzeError: msg, isAnalyzing: false });
        }
      },

      clearResults: () => set({ results: null, lastRunKey: null }),

      resetAll: () =>
        set({
          currentStep: 0,
          boltConfig: { ...DEFAULT_BOLT },
          jointConfig: { ...DEFAULT_JOINT, layers: [{ ...DEFAULT_JOINT.layers[0] }] },
          loadCases: [{ ...DEFAULT_LOAD_CASE }],
          fos: { ...DEFAULT_FOS },
          reportMeta: { ...DEFAULT_META },
          groups: {},
          results: null,
          lastRunKey: null,
          analyzeError: null,
          standard: "VDI",
        }),

      importConfig: (cfg) => set((s) => ({ ...s, ...cfg })),
    }),
    {
      name: "boltsizer-v2",
      version: 3,
      // Results are cheap to recompute and can be large — don't persist them.
      partialize: (s) => ({
        currentStep: Math.min(s.currentStep, 2),
        boltConfig: s.boltConfig,
        jointConfig: s.jointConfig,
        loadCases: s.loadCases,
        fos: s.fos,
        reportMeta: s.reportMeta,
        groups: s.groups,
        standard: s.standard,
      }),
      // Deep-merge persisted config over defaults so states saved by older
      // versions gain newly added fields instead of dropping them.
      merge: (persisted, current) => {
        const p = (persisted ?? {}) as Partial<AppState>;
        return {
          ...current,
          ...p,
          boltConfig: { ...current.boltConfig, ...(p.boltConfig ?? {}) },
          jointConfig: { ...current.jointConfig, ...(p.jointConfig ?? {}) },
          fos: { ...current.fos, ...(p.fos ?? {}) },
          reportMeta: { ...current.reportMeta, ...(p.reportMeta ?? {}) },
          loadCases: (p.loadCases ?? current.loadCases).map((lc) => ({
            ...DEFAULT_LOAD_CASE,
            ...lc,
          })),
        };
      },
    }
  )
);

/** True when inputs differ from the run behind the displayed results. */
export function useResultsStale(): boolean {
  return useAppStore((s) => {
    if (!s.results || !s.lastRunKey) return false;
    return (
      requestKey({
        boltConfig: s.boltConfig,
        jointConfig: s.jointConfig,
        loadCases: s.loadCases,
        standard: s.standard,
        fos: s.fos,
      }) !== s.lastRunKey
    );
  });
}

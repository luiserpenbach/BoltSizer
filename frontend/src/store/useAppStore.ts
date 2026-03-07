import { create } from "zustand";
import type { BoltConfig, JointConfig, LoadCase, AnalysisResults } from "../types";
import { runAnalysis, buildAnalyzeReq } from "../api/client";

export interface AppState {
  currentStep: number;
  boltConfig: BoltConfig;
  jointConfig: JointConfig;
  loadCases: LoadCase[];
  results: AnalysisResults | null;
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
  runAnalysis: () => Promise<void>;
  clearResults: () => void;
  importConfig: (cfg: Partial<AppState>) => void;
}

const DEFAULT_BOLT: BoltConfig = {
  designation: "M12",
  grade: "ISO 10.9",
  shank_length_mm: 20,
  threaded_length_mm: 15,
  nut_factor_K: 0.16,
  assembly_torque_Nmm: 85000,
  target_preload_N: 30000,
  use_target_preload: false,
  tightening_method: "torque_wrench",
  num_mating_surfaces: 2,
  surface_roughness_Rz: 6.3,
  coating: "Cadmium plated",
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
};

const DEFAULT_LOAD_CASE: LoadCase = {
  case_name: "LC1",
  axial_force_N: 10000,
  bending_moment_Nmm: 0,
  shear_force_N: 5000,
  torsion_Nmm: 0,
  load_factor: 1.5,
};

export const useAppStore = create<AppState>((set, get) => ({
  currentStep: 0,
  boltConfig: DEFAULT_BOLT,
  jointConfig: DEFAULT_JOINT,
  loadCases: [{ ...DEFAULT_LOAD_CASE }],
  results: null,
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

  runAnalysis: async () => {
    const { boltConfig, jointConfig, loadCases, standard } = get();
    set({ isAnalyzing: true, analyzeError: null, results: null });
    try {
      const req = buildAnalyzeReq(boltConfig, jointConfig, loadCases, standard);
      const results = await runAnalysis(req);
      set({ results, isAnalyzing: false, currentStep: 3 });
    } catch (e: unknown) {
      const msg =
        e instanceof Error ? e.message : "Analysis failed — check inputs";
      set({ analyzeError: msg, isAnalyzing: false });
    }
  },

  clearResults: () => set({ results: null }),

  importConfig: (cfg) => set((s) => ({ ...s, ...cfg })),
}));

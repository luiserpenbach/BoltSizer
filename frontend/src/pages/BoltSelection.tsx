import { useEffect, useState, useCallback, useRef } from "react";
import {
  FormGroup,
  HTMLSelect,
  NumericInput,
  Switch,
  Button,
  Callout,
  Spinner,
} from "@blueprintjs/core";
import { MetricCard } from "../components/shared/MetricCard";
import { useAppStore } from "../store/useAppStore";
import { fetchBolts, fetchMaterials, fetchCoatings, fetchTighteningMethods, previewPreload } from "../api/client";
import type { BoltLibraryEntry, MaterialEntry, CoatingEntry, TighteningMethod, PreloadPreview } from "../types";

type BoltLibrary = Record<string, BoltLibraryEntry>;
type MaterialLibrary = Record<string, MaterialEntry>;
type CoatingLibrary = Record<string, CoatingEntry>;
type TighteningLibrary = Record<string, TighteningMethod>;

const STANDARDS = ["ISO Metric (coarse)", "ISO Metric (fine)", "Unified (UNC/UNF)"];

function getBoltsByStandard(lib: BoltLibrary, std: string) {
  const map: Record<string, string> = {
    "ISO Metric (coarse)": "ISO metric",
    "ISO Metric (fine)": "ISO metric fine",
    "Unified (UNC/UNF)": "Unified",
  };
  return Object.keys(lib)
    .filter((k) => lib[k].standard === map[std])
    .sort();
}

export function BoltSelection() {
  const { boltConfig, jointConfig, setBoltConfig, setCurrentStep } = useAppStore();

  const [bolts, setBolts] = useState<BoltLibrary>({});
  const [materials, setMaterials] = useState<MaterialLibrary>({});
  const [coatings, setCoatings] = useState<CoatingLibrary>({});
  const [tightening, setTightening] = useState<TighteningLibrary>({});
  const [standard, setStandard] = useState("ISO Metric (coarse)");
  const [preview, setPreview] = useState<PreloadPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Load reference data on mount
  useEffect(() => {
    Promise.all([fetchBolts(), fetchMaterials(), fetchCoatings(), fetchTighteningMethods()])
      .then(([b, m, c, t]) => { setBolts(b); setMaterials(m); setCoatings(c); setTightening(t); })
      .catch((e) => setPreviewError(`Failed to load reference data: ${e.message}`));
  }, []);

  // Debounce timer ref
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runPreview = useCallback(() => {
    if (!boltConfig.designation || !boltConfig.grade) return;
    setPreviewLoading(true);
    setPreviewError(null);
    previewPreload({
      designation: boltConfig.designation,
      grade: boltConfig.grade,
      shank_length_mm: boltConfig.shank_length_mm,
      threaded_length_mm: boltConfig.threaded_length_mm,
      nut_factor_K: boltConfig.nut_factor_K,
      assembly_torque_Nmm: boltConfig.use_target_preload ? 0 : boltConfig.assembly_torque_Nmm,
      target_preload_N: boltConfig.use_target_preload ? boltConfig.target_preload_N : 0,
      tightening_method: boltConfig.tightening_method,
      num_mating_surfaces: boltConfig.num_mating_surfaces,
      surface_roughness_Rz: boltConfig.surface_roughness_Rz,
      grip_length_mm: jointConfig.layers.reduce((s, l) => s + l.thickness_mm, 0),
      layers: jointConfig.layers,
    })
      .then(setPreview)
      .catch((e) => setPreviewError(e.message ?? "Preview failed"))
      .finally(() => setPreviewLoading(false));
  }, [boltConfig, jointConfig]);

  // Debounced effect
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(runPreview, 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [runPreview]);

  const designationOptions = Object.keys(bolts).length
    ? getBoltsByStandard(bolts, standard)
    : [];
  const bdata = bolts[boltConfig.designation];
  const mdata = materials[boltConfig.grade];
  const cdata = coatings[boltConfig.coating];
  const tdata = tightening[boltConfig.tightening_method];

  const utilPct = preview?.proof_utilisation_pct ?? 0;
  const utilVariant = utilPct > 100 ? "danger" : utilPct > 90 ? "warn" : "default";
  const utilBarClass = utilPct > 100 ? "danger" : utilPct > 90 ? "warn" : "ok";

  return (
    <div className="two-col">
      {/* ---- Left: inputs ---- */}
      <div>
        <div className="section-heading">Bolt Specification</div>

        <FormGroup label="Thread Standard">
          <HTMLSelect
            value={standard}
            onChange={(e) => {
              setStandard(e.target.value);
              const opts = getBoltsByStandard(bolts, e.target.value);
              if (opts.length) setBoltConfig({ designation: opts[0] });
            }}
            options={STANDARDS}
            fill
          />
        </FormGroup>

        <FormGroup
          label="Bolt Designation"
          helperText={
            bdata ? (
              <span className="mono" style={{ fontSize: 11 }}>
                d = {bdata.nominal_diameter.toFixed(1)} mm | pitch = {bdata.pitch.toFixed(2)} mm | A_s = {bdata.stress_area.toFixed(1)} mm²
              </span>
            ) : null
          }
        >
          <HTMLSelect
            value={boltConfig.designation}
            onChange={(e) => setBoltConfig({ designation: e.target.value })}
            options={designationOptions}
            fill
          />
        </FormGroup>

        <FormGroup
          label="Material Grade"
          helperText={
            mdata ? (
              <span className="mono" style={{ fontSize: 11 }}>
                σ_y = {mdata.yield_strength} MPa | UTS = {mdata.uts} MPa | E = {(mdata.youngs_modulus / 1000).toFixed(0)} GPa
              </span>
            ) : null
          }
        >
          <HTMLSelect
            value={boltConfig.grade}
            onChange={(e) => setBoltConfig({ grade: e.target.value })}
            options={Object.keys(materials)}
            fill
          />
        </FormGroup>

        <div className="two-col-equal">
          <FormGroup label="Shank length [mm]">
            <NumericInput
              value={boltConfig.shank_length_mm}
              min={0}
              max={500}
              stepSize={1}
              onValueChange={(v) => setBoltConfig({ shank_length_mm: v })}
              fill
            />
          </FormGroup>
          <FormGroup label="Threaded engagement [mm]">
            <NumericInput
              value={boltConfig.threaded_length_mm}
              min={1}
              max={500}
              stepSize={1}
              onValueChange={(v) => setBoltConfig({ threaded_length_mm: v })}
              fill
            />
          </FormGroup>
        </div>

        <div className="section-heading">Surface & Lubrication</div>

        <FormGroup
          label="Coating / Lubrication"
          helperText={
            cdata ? (
              <span className="mono" style={{ fontSize: 11 }}>
                K = {cdata.k_nom.toFixed(2)} (range {cdata.k_min.toFixed(2)}–{cdata.k_max.toFixed(2)}) — {cdata.description}
              </span>
            ) : null
          }
        >
          <HTMLSelect
            value={boltConfig.coating}
            onChange={(e) => {
              const c = e.target.value;
              const kNom = coatings[c]?.k_nom ?? 0.16;
              setBoltConfig({ coating: c, nut_factor_K: kNom });
            }}
            options={Object.keys(coatings)}
            fill
          />
        </FormGroup>

        <FormGroup label="Nut/K-factor (override)">
          <NumericInput
            value={boltConfig.nut_factor_K}
            min={0.01}
            max={0.5}
            stepSize={0.01}
            minorStepSize={0.001}
            onValueChange={(v) => setBoltConfig({ nut_factor_K: v })}
            fill
          />
        </FormGroup>

        <div className="section-heading">Tightening Method</div>

        <FormGroup
          label="Tightening Method"
          helperText={
            tdata ? (
              <span className="mono" style={{ fontSize: 11 }}>
                α_A = {tdata.alpha_A.toFixed(2)} — {tdata.description}
              </span>
            ) : null
          }
        >
          <HTMLSelect
            value={boltConfig.tightening_method}
            onChange={(e) => setBoltConfig({ tightening_method: e.target.value })}
            options={Object.entries(tightening).map(([k, v]) => ({
              label: v.label,
              value: k,
            }))}
            fill
          />
        </FormGroup>

        <div className="section-heading">Assembly Loading</div>

        <Switch
          checked={boltConfig.use_target_preload}
          onChange={(e) => setBoltConfig({ use_target_preload: e.currentTarget.checked })}
          label="Enter target preload instead of torque"
          style={{ marginBottom: 12 }}
        />

        {boltConfig.use_target_preload ? (
          <FormGroup label="Target preload F_M [N]">
            <NumericInput
              value={boltConfig.target_preload_N}
              min={0}
              max={10000000}
              stepSize={100}
              onValueChange={(v) => setBoltConfig({ target_preload_N: v })}
              fill
            />
          </FormGroup>
        ) : (
          <FormGroup label="Assembly torque M_A [N·mm]">
            <NumericInput
              value={boltConfig.assembly_torque_Nmm}
              min={0}
              max={100000000}
              stepSize={500}
              onValueChange={(v) => setBoltConfig({ assembly_torque_Nmm: v })}
              fill
            />
          </FormGroup>
        )}

        <div className="two-col-equal">
          <FormGroup label="Mating surfaces">
            <NumericInput
              value={boltConfig.num_mating_surfaces}
              min={1}
              max={10}
              stepSize={1}
              onValueChange={(v) => setBoltConfig({ num_mating_surfaces: v })}
              fill
            />
          </FormGroup>
          <FormGroup label="Surface roughness Rz [μm]">
            <NumericInput
              value={boltConfig.surface_roughness_Rz}
              min={0.5}
              max={100}
              stepSize={0.5}
              onValueChange={(v) => setBoltConfig({ surface_roughness_Rz: v })}
              fill
            />
          </FormGroup>
        </div>

        <div className="page-actions">
          <Button
            intent="primary"
            rightIcon="arrow-right"
            onClick={() => setCurrentStep(1)}
          >
            Joint Geometry
          </Button>
        </div>
      </div>

      {/* ---- Right: live preview ---- */}
      <div>
        <div className="section-heading">
          Preload Preview
          {previewLoading && <Spinner size={12} style={{ display: "inline-block", marginLeft: 8 }} />}
        </div>

        {previewError && (
          <Callout intent="danger" style={{ marginBottom: 12 }}>
            {previewError}
          </Callout>
        )}

        {preview && (
          <>
            <div className="metric-grid">
              <MetricCard
                label="Assembly Preload F_M_max"
                value={`${preview.F_M_max.toLocaleString(undefined, { maximumFractionDigits: 0 })} N`}
              />
              <MetricCard
                label="Scatter α_A"
                value={preview.alpha_A.toFixed(2)}
                sub={`F_M_min = ${preview.F_M_min.toLocaleString(undefined, { maximumFractionDigits: 0 })} N`}
              />
              <MetricCard
                label="Embedding loss F_Z"
                value={`${preview.F_Z.toLocaleString(undefined, { maximumFractionDigits: 0 })} N`}
                sub={`Net F_V_min = ${preview.F_preload_min.toLocaleString(undefined, { maximumFractionDigits: 0 })} N`}
              />
              <MetricCard
                label="Proof utilisation"
                value={`${utilPct.toFixed(1)}%`}
                variant={utilVariant}
              />
            </div>

            <div className="util-bar-wrap">
              <div className="util-bar-label">
                Proof load utilisation: {utilPct.toFixed(1)}%
              </div>
              <div className="util-bar">
                <div
                  className={`util-bar-fill ${utilBarClass}`}
                  style={{ width: `${Math.min(utilPct, 100)}%` }}
                />
              </div>
            </div>

            {utilPct > 90 && (
              <Callout intent="warning" style={{ marginTop: 12, fontSize: 12 }}>
                Assembly preload exceeds 90% of proof load. ECSS-E-HB-32-23A prohibits
                torque-to-yield tightening for space hardware. Consider reducing torque
                or using a larger bolt.
              </Callout>
            )}

            <div style={{ marginTop: 16 }}>
              <div className="section-heading" style={{ marginTop: 0 }}>Preload Budget</div>
              <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                <tbody>
                  {[
                    ["F_M_nominal", `${preview.F_M_nominal.toFixed(0)} N`, "Nominal assembly preload"],
                    ["F_M_max", `${preview.F_M_max.toFixed(0)} N`, "Max with scatter"],
                    ["F_M_min", `${preview.F_M_min.toFixed(0)} N`, "Min with scatter"],
                    ["F_Z (embedding)", `−${preview.F_Z.toFixed(0)} N`, "Embedding relaxation"],
                    ["F_V_min (working)", `${preview.F_preload_min.toFixed(0)} N`, "Net working preload"],
                    ["A_s", `${preview.stress_area_mm2.toFixed(1)} mm²`, "Tensile stress area"],
                    ["σ_proof", `${preview.proof_load_stress_MPa.toFixed(0)} MPa`, "Proof load stress"],
                  ].map(([label, value, note]) => (
                    <tr key={label} style={{ borderBottom: "1px solid var(--border-color)" }}>
                      <td style={{ padding: "5px 0", color: "var(--text-muted)", width: "40%" }}>{label}</td>
                      <td className="mono" style={{ padding: "5px 6px", color: "var(--text-primary)", textAlign: "right" }}>{value}</td>
                      <td style={{ padding: "5px 0 5px 8px", color: "var(--text-muted)", fontSize: 11 }}>{note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {!preview && !previewLoading && !previewError && (
          <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
            Enter bolt parameters to see the live preload preview.
          </div>
        )}
      </div>
    </div>
  );
}

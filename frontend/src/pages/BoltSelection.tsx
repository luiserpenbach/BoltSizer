import { useEffect, useState, useCallback, useRef } from "react";
import {
  FormGroup,
  HTMLSelect,
  NumericInput,
  Switch,
  Button,
  Callout,
  Spinner,
  Collapse,
} from "@blueprintjs/core";
import { MetricCard } from "../components/shared/MetricCard";
import { useAppStore } from "../store/useAppStore";
import { fetchBolts, fetchMaterials, fetchCoatings, fetchTighteningMethods, previewPreload, resolveHeadBearingDiameter } from "../api/client";
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
  const [advancedOpen, setAdvancedOpen] = useState(false);

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
    const useRange = boltConfig.use_friction_range && boltConfig.nut_factor_K_min != null;
    previewPreload({
      designation: boltConfig.designation,
      grade: boltConfig.grade,
      shank_length_mm: boltConfig.shank_length_mm,
      threaded_length_mm: boltConfig.threaded_length_mm,
      nut_factor_K: boltConfig.nut_factor_K,
      nut_factor_K_min: useRange ? boltConfig.nut_factor_K_min : null,
      nut_factor_K_max: useRange ? boltConfig.nut_factor_K_max : null,
      tool_scatter_pct: useRange ? boltConfig.tool_scatter_pct / 100 : null,
      assembly_torque_Nmm: boltConfig.use_target_preload ? 0 : boltConfig.assembly_torque_Nmm,
      target_preload_N: boltConfig.use_target_preload ? boltConfig.target_preload_N : 0,
      tightening_method: boltConfig.tightening_method,
      num_mating_surfaces: boltConfig.num_mating_surfaces,
      surface_roughness_Rz: boltConfig.surface_roughness_Rz,
      grip_length_mm: jointConfig.layers.reduce((s, l) => s + l.thickness_mm, 0),
      layers: jointConfig.layers,
      head_bearing_diameter_mm: resolveHeadBearingDiameter(boltConfig),
      hole_diameter_mm: boltConfig.hole_diameter_mm,
      thread_rolled: boltConfig.thread_rolled,
      embedding_percent_of_max:
        boltConfig.embedding_mode === "percent" ? boltConfig.embedding_percent / 100 : null,
      custom_material: boltConfig.grade === "Custom" ? boltConfig.custom_material : null,
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
            onChange={(e) => {
              const g = e.target.value;
              setBoltConfig({
                grade: g,
                custom_material:
                  g === "Custom"
                    ? boltConfig.custom_material ?? {
                        yield_strength_MPa: 640,
                        uts_MPa: 800,
                        youngs_modulus_MPa: 210000,
                        proof_load_stress_MPa: null,
                        fatigue_limit_MPa: null,
                        cte_per_K: null,
                      }
                    : boltConfig.custom_material,
              });
            }}
            options={Object.keys(materials)}
            fill
          />
        </FormGroup>

        {boltConfig.grade === "Custom" && boltConfig.custom_material && (
          <div
            style={{
              border: "1px solid var(--border-color)",
              borderRadius: 3,
              padding: 12,
              marginBottom: 14,
              background: "var(--bg-surface)",
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8 }}>
              Custom material properties
            </div>
            <div className="two-col-equal">
              <FormGroup label="Yield R_p0.2 [MPa]">
                <NumericInput
                  value={boltConfig.custom_material.yield_strength_MPa}
                  min={1} max={3000} stepSize={10} majorStepSize={100}
                  onValueChange={(v) =>
                    setBoltConfig({ custom_material: { ...boltConfig.custom_material!, yield_strength_MPa: v } })}
                  fill
                />
              </FormGroup>
              <FormGroup label="Ultimate R_m [MPa]">
                <NumericInput
                  value={boltConfig.custom_material.uts_MPa}
                  min={1} max={3000} stepSize={10} majorStepSize={100}
                  onValueChange={(v) =>
                    setBoltConfig({ custom_material: { ...boltConfig.custom_material!, uts_MPa: v } })}
                  fill
                />
              </FormGroup>
            </div>
            <div className="two-col-equal">
              <FormGroup label="E [MPa]">
                <NumericInput
                  value={boltConfig.custom_material.youngs_modulus_MPa}
                  min={1000} max={500000} stepSize={1000} majorStepSize={10000}
                  onValueChange={(v) =>
                    setBoltConfig({ custom_material: { ...boltConfig.custom_material!, youngs_modulus_MPa: v } })}
                  fill
                />
              </FormGroup>
              <FormGroup
                label="Thread fatigue σ_AS [MPa]"
                helperText="Optional. Fastener test data only — never smooth-bar values. Blank = VDI thread formula."
              >
                <NumericInput
                  value={boltConfig.custom_material.fatigue_limit_MPa ?? undefined}
                  placeholder="VDI formula"
                  min={1} max={1000} stepSize={5} majorStepSize={25}
                  onValueChange={(v, str) =>
                    setBoltConfig({
                      custom_material: {
                        ...boltConfig.custom_material!,
                        fatigue_limit_MPa: str === "" || Number.isNaN(v) ? null : v,
                      },
                    })}
                  fill
                />
              </FormGroup>
            </div>
          </div>
        )}

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
              const entry = coatings[c];
              setBoltConfig({
                coating: c,
                nut_factor_K: entry?.k_nom ?? 0.16,
                nut_factor_K_min: entry?.k_min ?? null,
                nut_factor_K_max: entry?.k_max ?? null,
              });
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
            majorStepSize={0.05}
            onValueChange={(v) => setBoltConfig({ nut_factor_K: v })}
            fill
          />
        </FormGroup>

        <Switch
          checked={boltConfig.use_friction_range}
          onChange={(e) => setBoltConfig({ use_friction_range: e.currentTarget.checked })}
          labelElement={
            <span>
              Use coating friction range{" "}
              {cdata && (
                <span className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  (K {cdata.k_min.toFixed(2)}–{cdata.k_max.toFixed(2)} brackets the preload)
                </span>
              )}
            </span>
          }
          style={{ marginBottom: 8 }}
        />
        {boltConfig.use_friction_range && (
          <FormGroup
            label="Torque tool scatter [±%]"
            helperText="Composed with the friction extremes (ECSS convention): F_max = M·(1+s)/(K_min·d)."
          >
            <NumericInput
              value={boltConfig.tool_scatter_pct}
              min={0}
              max={25}
              stepSize={1}
              minorStepSize={0.5}
              majorStepSize={5}
              onValueChange={(v) => !Number.isNaN(v) && setBoltConfig({ tool_scatter_pct: v })}
              fill
            />
          </FormGroup>
        )}

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

        <Button
          minimal
          small
          icon={advancedOpen ? "chevron-down" : "chevron-right"}
          onClick={() => setAdvancedOpen(!advancedOpen)}
          style={{ marginTop: 4 }}
        >
          Advanced bolt options
        </Button>
        <Collapse isOpen={advancedOpen}>
          <div
            style={{
              border: "1px solid var(--border-color)",
              borderRadius: 3,
              padding: 12,
              marginTop: 8,
              background: "var(--bg-surface)",
            }}
          >
            <div className="two-col-equal">
              <FormGroup
                label="Head style"
                helperText="Sets the bearing face diameter d_w (surface pressure + stiffness)."
              >
                <HTMLSelect
                  value={boltConfig.head_style}
                  onChange={(e) => setBoltConfig({ head_style: e.target.value as "hex" | "din912" | "custom" })}
                  options={[
                    { label: "Hex (ISO 4014)", value: "hex" },
                    { label: "Socket head (DIN 912)", value: "din912" },
                    { label: "Custom d_w", value: "custom" },
                  ]}
                  fill
                />
              </FormGroup>
              {boltConfig.head_style === "custom" ? (
                <FormGroup label="Bearing face d_w [mm]">
                  <NumericInput
                    value={boltConfig.head_bearing_diameter_mm ?? undefined}
                    min={1} max={200} stepSize={0.5} minorStepSize={0.1} majorStepSize={5}
                    onValueChange={(v) => !Number.isNaN(v) && setBoltConfig({ head_bearing_diameter_mm: v })}
                    fill
                  />
                </FormGroup>
              ) : (
                <FormGroup label="Clearance hole d_h [mm]" helperText="Blank = ISO 273 medium">
                  <NumericInput
                    value={boltConfig.hole_diameter_mm ?? undefined}
                    placeholder="auto"
                    min={1} max={200} stepSize={0.5} minorStepSize={0.1} majorStepSize={5}
                    onValueChange={(v, str) =>
                      setBoltConfig({ hole_diameter_mm: str === "" || Number.isNaN(v) ? null : v })}
                    fill
                  />
                </FormGroup>
              )}
            </div>
            <div className="two-col-equal">
              <FormGroup
                label="Thread rolling"
                helperText="Rolled after heat treatment raises the fatigue allowable (VDI §5.5.3)."
              >
                <HTMLSelect
                  value={boltConfig.thread_rolled}
                  onChange={(e) => setBoltConfig({ thread_rolled: e.target.value as "before_ht" | "after_ht" })}
                  options={[
                    { label: "Rolled before HT (standard)", value: "before_ht" },
                    { label: "Rolled after HT (aerospace)", value: "after_ht" },
                  ]}
                  fill
                />
              </FormGroup>
              <FormGroup
                label="Embedding model"
                helperText={boltConfig.embedding_mode === "percent" ? "F_Z = % of max preload" : "VDI 2230 Table 5.4 guide values"}
              >
                <div style={{ display: "flex", gap: 8 }}>
                  <HTMLSelect
                    value={boltConfig.embedding_mode}
                    onChange={(e) => setBoltConfig({ embedding_mode: e.target.value as "vdi" | "percent" })}
                    options={[
                      { label: "VDI table", value: "vdi" },
                      { label: "% of preload", value: "percent" },
                    ]}
                  />
                  {boltConfig.embedding_mode === "percent" && (
                    <NumericInput
                      value={boltConfig.embedding_percent}
                      min={0} max={20} stepSize={0.5} minorStepSize={0.1} majorStepSize={2}
                      onValueChange={(v) => !Number.isNaN(v) && setBoltConfig({ embedding_percent: v })}
                      style={{ width: 80 }}
                    />
                  )}
                </div>
              </FormGroup>
            </div>
          </div>
        </Collapse>

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
              majorStepSize={1000}
              onValueChange={(v) => setBoltConfig({ target_preload_N: v })}
              fill
            />
          </FormGroup>
        ) : (
          <FormGroup
            label="Assembly torque M_A [N·m]"
            helperText={
              <span className="mono" style={{ fontSize: 11 }}>
                = {boltConfig.assembly_torque_Nmm.toLocaleString()} N·mm
              </span>
            }
          >
            <NumericInput
              value={boltConfig.assembly_torque_Nmm / 1000}
              min={0}
              max={100000}
              stepSize={0.5}
              minorStepSize={0.1}
              majorStepSize={5}
              onValueChange={(v) => !Number.isNaN(v) && setBoltConfig({ assembly_torque_Nmm: Math.round(v * 1000) })}
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

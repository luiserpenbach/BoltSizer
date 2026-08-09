import { useEffect, useState, useCallback, useRef } from "react";
import {
  FormGroup,
  HTMLSelect,
  NumericInput,
  Button,
  Callout,
  Spinner,
  Switch,
} from "@blueprintjs/core";
import { MetricCard } from "../components/shared/MetricCard";
import { LayerEditor } from "../components/shared/LayerEditor";
import { BoltCircleViz } from "../components/charts/BoltCircleViz";
import { useAppStore } from "../store/useAppStore";
import { fetchFlangeMaterials, previewStiffness, resolveHeadBearingDiameter } from "../api/client";
import type { StiffnessPreview } from "../types";

// Interface friction guide values (editable; verify by test for
// slip-critical joints)
const INTERFACE_OPTIONS = {
  "bare metal": 0.12,
  "degreased / cleaned": 0.2,
  "anodised aluminium": 0.1,
  "alodine / chromate (Al)": 0.15,
  "zinc plated": 0.15,
  "painted": 0.08,
  "sandblasted": 0.35,
  "knurled": 0.25,
  "lubricated / greased": 0.08,
  "MoS2 coated": 0.05,
};

// Typical minimum yield strengths for the flange material list [MPa].
// Guide values for the auto-derived bearing check — override as needed.
const FLANGE_YIELD_GUIDE: Record<string, number> = {
  "Steel (carbon)": 235,
  "Steel (stainless)": 190,
  "Aluminium alloy": 240,
  "Titanium alloy": 830,
  "Inconel 718": 1034,
  "Copper alloy": 195,
  "Cast iron": 200,
};

export function JointGeometry() {
  const { boltConfig, jointConfig, setJointConfig, setCurrentStep } = useAppStore();

  // Auto-derive bearing-check inputs from the stack
  const derivedThinnest = jointConfig.layers.length
    ? Math.min(...jointConfig.layers.map((l) => l.thickness_mm))
    : jointConfig.plate_thickness_mm;
  const thinnestLayer = jointConfig.layers.find((l) => l.thickness_mm === derivedThinnest);
  const derivedYield = thinnestLayer
    ? FLANGE_YIELD_GUIDE[thinnestLayer.material] ?? jointConfig.plate_yield_strength_MPa
    : jointConfig.plate_yield_strength_MPa;

  useEffect(() => {
    if (!jointConfig.auto_bearing) return;
    if (
      jointConfig.plate_thickness_mm !== derivedThinnest ||
      jointConfig.plate_yield_strength_MPa !== derivedYield
    ) {
      setJointConfig({
        plate_thickness_mm: derivedThinnest,
        plate_yield_strength_MPa: derivedYield,
      });
    }
  }, [jointConfig.auto_bearing, derivedThinnest, derivedYield]); // eslint-disable-line react-hooks/exhaustive-deps

  const [flangeMats, setFlangeMats] = useState<Record<string, number>>({});
  const [preview, setPreview] = useState<StiffnessPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    fetchFlangeMaterials().then(setFlangeMats);
  }, []);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runPreview = useCallback(() => {
    if (!boltConfig.designation || !boltConfig.grade || jointConfig.layers.length === 0) return;
    setPreviewLoading(true);
    setPreviewError(null);
    previewStiffness({
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
      num_bolts: jointConfig.num_bolts,
      bolt_circle_diameter_mm: jointConfig.bolt_circle_diameter_mm,
      layers: jointConfig.layers,
      interface_treatment: jointConfig.interface_treatment,
      friction_coefficient: jointConfig.friction_coefficient,
      num_friction_interfaces: jointConfig.num_friction_interfaces,
      load_intro_factor_n: jointConfig.load_intro_factor_n,
      available_flange_diameter_mm: jointConfig.available_flange_diameter_mm,
      head_bearing_diameter_mm: resolveHeadBearingDiameter(boltConfig),
      hole_diameter_mm: boltConfig.hole_diameter_mm,
    })
      .then(setPreview)
      .catch((e) => setPreviewError(e.message ?? "Preview failed"))
      .finally(() => setPreviewLoading(false));
  }, [boltConfig, jointConfig]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(runPreview, 500);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [runPreview]);

  return (
    <div className="two-col">
      {/* ---- Left: inputs ---- */}
      <div>
        <div className="section-heading">Bolt Circle</div>
        <div className="two-col-equal">
          <FormGroup label="Number of bolts">
            <NumericInput
              value={jointConfig.num_bolts}
              min={1}
              max={48}
              stepSize={1}
              onValueChange={(v) => setJointConfig({ num_bolts: v })}
              fill
            />
          </FormGroup>
          <FormGroup label="PCD (bolt circle diameter) [mm]">
            <NumericInput
              value={jointConfig.bolt_circle_diameter_mm}
              min={1}
              max={5000}
              stepSize={1}
              onValueChange={(v) => setJointConfig({ bolt_circle_diameter_mm: v })}
              fill
            />
          </FormGroup>
        </div>

        <div className="section-heading">Clamped Stack (Layers)</div>
        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 0 }}>
          Define each layer from bolt head to nut. Layer order does not affect the calculation.
        </p>
        {Object.keys(flangeMats).length > 0 ? (
          <LayerEditor
            layers={jointConfig.layers}
            flangeMaterials={flangeMats}
            onChange={(layers) => setJointConfig({ layers })}
          />
        ) : (
          <Spinner size={20} />
        )}

        <div className="section-heading">Interface Treatment & Friction</div>
        <div className="two-col-equal">
          <FormGroup label="Interface treatment">
            <HTMLSelect
              value={jointConfig.interface_treatment}
              onChange={(e) => {
                const t = e.target.value;
                const mu = INTERFACE_OPTIONS[t as keyof typeof INTERFACE_OPTIONS] ?? jointConfig.friction_coefficient;
                setJointConfig({ interface_treatment: t, friction_coefficient: mu });
              }}
              options={Object.keys(INTERFACE_OPTIONS)}
              fill
            />
          </FormGroup>
          <FormGroup label="Friction coefficient μ">
            <NumericInput
              value={jointConfig.friction_coefficient}
              min={0.01}
              max={1.0}
              stepSize={0.01}
              minorStepSize={0.005}
              onValueChange={(v) => setJointConfig({ friction_coefficient: v })}
              fill
            />
          </FormGroup>
        </div>
        <FormGroup label="Number of friction interfaces n_i">
          <NumericInput
            value={jointConfig.num_friction_interfaces}
            min={1}
            max={8}
            stepSize={1}
            onValueChange={(v) => setJointConfig({ num_friction_interfaces: v })}
            fill
          />
        </FormGroup>

        <div className="section-heading">Joint Type &amp; Cone Limit</div>
        <div className="two-col-equal">
          <FormGroup
            label="Joint type"
            helperText={
              jointConfig.joint_type === "tapped"
                ? "Tapped: thread-stripping check enabled."
                : "Through-bolt with matching nut (no stripping check needed)."
            }
          >
            <HTMLSelect
              value={jointConfig.joint_type}
              onChange={(e) => setJointConfig({ joint_type: e.target.value as "through" | "tapped" })}
              options={[
                { label: "Through-bolt (nut)", value: "through" },
                { label: "Tapped / blind hole", value: "tapped" },
              ]}
              fill
            />
          </FormGroup>
          <FormGroup
            label="Available diameter D_A [mm]"
            helperText="Cone limit ≈ min(bolt pitch, 2×edge distance). Blank = unlimited (wide flange)."
          >
            <NumericInput
              value={jointConfig.available_flange_diameter_mm ?? undefined}
              placeholder="unlimited"
              min={1}
              max={2000}
              stepSize={1}
              minorStepSize={0.5}
              majorStepSize={10}
              onValueChange={(v, str) =>
                setJointConfig({
                  available_flange_diameter_mm: str === "" || Number.isNaN(v) ? null : v,
                })}
              fill
            />
          </FormGroup>
        </div>
        {jointConfig.joint_type === "tapped" && (
          <div className="two-col-equal">
            <FormGroup label="Thread engagement L_e [mm]">
              <NumericInput
                value={jointConfig.tapped_engagement_length_mm}
                min={1}
                max={200}
                stepSize={0.5}
                minorStepSize={0.1}
                majorStepSize={5}
                onValueChange={(v) => !Number.isNaN(v) && setJointConfig({ tapped_engagement_length_mm: v })}
                fill
              />
            </FormGroup>
            <FormGroup
              label="Tapped material UTS [MPa]"
              helperText="Tensile ultimate of the insert / tapped part (e.g. AL6061-T6: 310)."
            >
              <NumericInput
                value={jointConfig.tapped_material_uts_MPa}
                min={50}
                max={2000}
                stepSize={10}
                majorStepSize={100}
                onValueChange={(v) => !Number.isNaN(v) && setJointConfig({ tapped_material_uts_MPa: v })}
                fill
              />
            </FormGroup>
          </div>
        )}

        <div className="section-heading">Load Introduction</div>
        <FormGroup
          label={`Load introduction factor n = ${jointConfig.load_intro_factor_n.toFixed(2)}`}
          helperText="0 = load at interface (conservative). 1 = load at bolt head/nut. VDI 2230 §5.3."
        >
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={jointConfig.load_intro_factor_n}
            onChange={(e) => setJointConfig({ load_intro_factor_n: parseFloat(e.target.value) })}
            style={{ width: "100%", accentColor: "var(--accent)", cursor: "pointer" }}
          />
        </FormGroup>

        <div className="section-heading">Plate Bearing Check</div>
        <Switch
          checked={jointConfig.auto_bearing}
          onChange={(e) => setJointConfig({ auto_bearing: e.currentTarget.checked })}
          label={`Derive from stack (thinnest layer ${derivedThinnest.toFixed(1)} mm${thinnestLayer ? `, ${thinnestLayer.material} σ_y ≈ ${derivedYield} MPa guide value` : ""})`}
          style={{ marginBottom: 8 }}
        />
        <div className="two-col-equal">
          <FormGroup label="Thinnest plate thickness [mm]">
            <NumericInput
              value={jointConfig.plate_thickness_mm}
              min={0.5}
              max={500}
              stepSize={0.5}
              majorStepSize={5}
              disabled={jointConfig.auto_bearing}
              onValueChange={(v) => setJointConfig({ plate_thickness_mm: v })}
              fill
            />
          </FormGroup>
          <FormGroup label="Plate yield strength [MPa]">
            <NumericInput
              value={jointConfig.plate_yield_strength_MPa}
              min={50}
              max={2000}
              stepSize={10}
              majorStepSize={100}
              disabled={jointConfig.auto_bearing}
              onValueChange={(v) => setJointConfig({ plate_yield_strength_MPa: v })}
              fill
            />
          </FormGroup>
        </div>

        <div className="page-actions">
          <Button minimal onClick={() => setCurrentStep(0)} icon="arrow-left">Bolt Selection</Button>
          <Button intent="primary" rightIcon="arrow-right" onClick={() => setCurrentStep(2)}>
            Loading
          </Button>
        </div>
      </div>

      {/* ---- Right: stiffness preview ---- */}
      <div>
        <div className="section-heading">
          Stiffness Preview
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
                label="Bolt compliance δ_S"
                value={preview.delta_S.toExponential(3)}
                sub="mm/N"
              />
              <MetricCard
                label="Clamped-part compliance δ_P"
                value={preview.delta_P.toExponential(3)}
                sub="mm/N"
              />
              <MetricCard
                label="Force ratio φ (basic)"
                value={preview.phi_basic.toFixed(4)}
                sub={`Bolt takes ${(preview.phi_basic * 100).toFixed(1)}% of ext. load`}
              />
              <MetricCard
                label="Force ratio φ_n (with n)"
                value={preview.phi_n.toFixed(4)}
                sub={`n = ${preview.load_intro_factor_n.toFixed(2)}`}
              />
            </div>

            <div className="util-bar-wrap">
              <div className="util-bar-label">
                Bolt load share: {(preview.phi_basic * 100).toFixed(1)}% | Plates: {((1 - preview.phi_basic) * 100).toFixed(1)}%
              </div>
              <div className="util-bar">
                <div
                  className="util-bar-fill ok"
                  style={{ width: `${preview.phi_basic * 100}%` }}
                />
              </div>
            </div>
          </>
        )}

        <div style={{ marginTop: 20 }}>
          <div className="section-heading" style={{ marginTop: 0 }}>Bolt Circle</div>
          <BoltCircleViz
            numBolts={jointConfig.num_bolts}
            pcd={jointConfig.bolt_circle_diameter_mm}
          />
        </div>
      </div>
    </div>
  );
}

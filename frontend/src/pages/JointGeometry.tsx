import { useEffect, useState, useCallback, useRef } from "react";
import {
  FormGroup,
  HTMLSelect,
  NumericInput,
  Button,
  Callout,
  Spinner,
} from "@blueprintjs/core";
import { MetricCard } from "../components/shared/MetricCard";
import { LayerEditor } from "../components/shared/LayerEditor";
import { BoltCircleViz } from "../components/charts/BoltCircleViz";
import { useAppStore } from "../store/useAppStore";
import { fetchFlangeMaterials, previewStiffness } from "../api/client";
import type { StiffnessPreview } from "../types";

const INTERFACE_OPTIONS = {
  "bare metal": 0.12,
  "anodised aluminium": 0.10,
  "painted": 0.08,
  "sandblasted": 0.35,
  "knurled": 0.25,
};

export function JointGeometry() {
  const { boltConfig, jointConfig, setJointConfig, setCurrentStep } = useAppStore();

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
        <div className="two-col-equal">
          <FormGroup label="Thinnest plate thickness [mm]">
            <NumericInput
              value={jointConfig.plate_thickness_mm}
              min={0.5}
              max={500}
              stepSize={0.5}
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

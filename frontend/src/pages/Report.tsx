import { useRef, useState } from "react";
import { Button, Callout, FileInput, FormGroup, InputGroup } from "@blueprintjs/core";
import { useAppStore } from "../store/useAppStore";
import { exportJson, exportPdf, importJson, buildAnalyzeReq, exportProjectPdf } from "../api/client";
import type { AnalyzeReq } from "../api/client";

export function Report() {
  const {
    boltConfig, jointConfig, loadCases, results, importConfig, setCurrentStep,
    standard, fos, reportMeta, setReportMeta, groups,
  } = useAppStore();
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const req = buildAnalyzeReq(boltConfig, jointConfig, loadCases, standard, fos, reportMeta);

  const handleExportPdf = async () => {
    setExporting(true);
    setError(null);
    try {
      await exportPdf(req);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "PDF export failed");
    } finally {
      setExporting(false);
    }
  };

  const handleProjectPdf = async () => {
    setExporting(true);
    setError(null);
    try {
      const names = Object.keys(groups);
      const groupReqs = names.map((n) => ({
        name: n,
        request: buildAnalyzeReq(
          groups[n].boltConfig, groups[n].jointConfig, groups[n].loadCases,
          groups[n].standard, groups[n].fos,
        ),
      }));
      // Always include the current (unsaved) configuration as its own group
      groupReqs.push({
        name: "Current configuration",
        request: req,
      });
      await exportProjectPdf(groupReqs, reportMeta);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Project PDF export failed");
    } finally {
      setExporting(false);
    }
  };

  const handleExportJson = async () => {
    setExporting(true);
    setError(null);
    try {
      await exportJson(req);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "JSON export failed");
    } finally {
      setExporting(false);
    }
  };

  const handleImportJson = async (file: File) => {
    setImporting(true);
    setError(null);
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const parsed: AnalyzeReq = await importJson(data);
      // Map back to store format
      importConfig({
        boltConfig: {
          ...boltConfig,
          designation: parsed.designation,
          grade: parsed.grade,
          shank_length_mm: parsed.shank_length_mm,
          threaded_length_mm: parsed.threaded_length_mm,
          nut_factor_K: parsed.nut_factor_K,
          nut_factor_K_min: parsed.nut_factor_K_min ?? null,
          nut_factor_K_max: parsed.nut_factor_K_max ?? null,
          use_friction_range: parsed.nut_factor_K_min != null,
          tool_scatter_pct: (parsed.tool_scatter_pct ?? 0.05) * 100,
          assembly_torque_Nmm: parsed.assembly_torque_Nmm,
          target_preload_N: parsed.target_preload_N,
          use_target_preload: parsed.target_preload_N > 0 && parsed.assembly_torque_Nmm === 0,
          tightening_method: parsed.tightening_method,
          num_mating_surfaces: parsed.num_mating_surfaces,
          surface_roughness_Rz: parsed.surface_roughness_Rz,
          head_bearing_diameter_mm: parsed.head_bearing_diameter_mm ?? null,
          head_style: parsed.head_bearing_diameter_mm != null ? "custom" : "hex",
          hole_diameter_mm: parsed.hole_diameter_mm ?? null,
          thread_rolled: parsed.thread_rolled ?? "before_ht",
          embedding_mode: parsed.embedding_percent_of_max != null ? "percent" : "vdi",
          embedding_percent: (parsed.embedding_percent_of_max ?? 0.05) * 100,
          custom_material: (parsed.custom_material ?? null) as typeof boltConfig.custom_material,
        },
        jointConfig: {
          ...jointConfig,
          num_bolts: parsed.num_bolts,
          bolt_circle_diameter_mm: parsed.bolt_circle_diameter_mm,
          layers: parsed.layers,
          interface_treatment: parsed.interface_treatment,
          friction_coefficient: parsed.friction_coefficient,
          num_friction_interfaces: parsed.num_friction_interfaces,
          load_intro_factor_n: parsed.load_intro_factor_n,
          plate_thickness_mm: parsed.plate_thickness_mm,
          plate_yield_strength_MPa: parsed.plate_yield_strength_MPa,
          auto_bearing: false,
          available_flange_diameter_mm: parsed.available_flange_diameter_mm ?? null,
          joint_type: parsed.tapped_engagement_length_mm != null ? "tapped" : "through",
          tapped_engagement_length_mm: parsed.tapped_engagement_length_mm ?? jointConfig.tapped_engagement_length_mm,
          tapped_material_uts_MPa: parsed.tapped_material_uts_MPa ?? jointConfig.tapped_material_uts_MPa,
        },
        loadCases: parsed.load_cases,
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  return (
    <div>
      <div className="section-heading" style={{ marginTop: 0 }}>Report Metadata</div>
      <div
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border-color)",
          borderRadius: 3,
          padding: 16,
          marginBottom: 24,
          display: "grid",
          gridTemplateColumns: "2fr 1fr 2fr",
          gap: 12,
        }}
      >
        <FormGroup label="Project name" style={{ marginBottom: 0 }}>
          <InputGroup
            value={reportMeta.project_name}
            placeholder="e.g. Chamber flange QM"
            onChange={(e) => setReportMeta({ project_name: e.target.value })}
          />
        </FormGroup>
        <FormGroup label="Revision" style={{ marginBottom: 0 }}>
          <InputGroup
            value={reportMeta.revision}
            placeholder="A"
            onChange={(e) => setReportMeta({ revision: e.target.value })}
          />
        </FormGroup>
        <FormGroup label="Engineer" style={{ marginBottom: 0 }}>
          <InputGroup
            value={reportMeta.engineer_name}
            placeholder="Name for the title block"
            onChange={(e) => setReportMeta({ engineer_name: e.target.value })}
          />
        </FormGroup>
      </div>

      <div className="section-heading">Export</div>

      <div style={{ display: "flex", gap: 12, marginBottom: 24 }}>
        <div
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border-color)",
            borderRadius: 3,
            padding: 20,
            flex: 1,
          }}
        >
          <div style={{ marginBottom: 8, fontWeight: 600 }}>PDF Calculation Report</div>
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 0, marginBottom: 16 }}>
            Generate a structured PDF report containing inputs, all margins of safety,
            the full calculation chain, and engineering warnings.
          </p>
          <Button
            intent="primary"
            icon="document"
            onClick={handleExportPdf}
            disabled={!results || exporting}
            loading={exporting}
            fill
          >
            Download PDF Report
          </Button>
          {!results && (
            <p style={{ fontSize: 11, color: "var(--warn-color)", marginTop: 8, marginBottom: 0 }}>
              Run the analysis first to generate a PDF.
            </p>
          )}
          <Button
            icon="projects"
            onClick={handleProjectPdf}
            disabled={exporting}
            loading={exporting}
            fill
            style={{ marginTop: 8 }}
          >
            Project report ({Object.keys(groups).length} saved group{Object.keys(groups).length === 1 ? "" : "s"} + current)
          </Button>
        </div>

        <div
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border-color)",
            borderRadius: 3,
            padding: 20,
            flex: 1,
          }}
        >
          <div style={{ marginBottom: 8, fontWeight: 600 }}>Save Case as JSON</div>
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 0, marginBottom: 16 }}>
            Export the current configuration (bolt, joint, load cases) as a JSON file
            for reproducibility and later reuse.
          </p>
          <Button
            icon="export"
            onClick={handleExportJson}
            disabled={exporting}
            loading={exporting}
            fill
          >
            Save as JSON
          </Button>
        </div>
      </div>

      <div className="section-heading">Import</div>

      <div
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border-color)",
          borderRadius: 3,
          padding: 20,
          marginBottom: 24,
        }}
      >
        <div style={{ marginBottom: 8, fontWeight: 600 }}>Load Case from JSON</div>
        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 0, marginBottom: 16 }}>
          Import a previously saved BoltSizer case. This will overwrite the current bolt,
          joint, and load case configuration.
        </p>
        <FileInput
          text="Choose JSON file…"
          inputProps={{ accept: ".json" }}
          disabled={importing}
          onInputChange={(e) => {
            const file = e.currentTarget.files?.[0];
            if (file) handleImportJson(file);
          }}
        />
        {importing && (
          <p style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 8 }}>
            Importing…
          </p>
        )}
      </div>

      {error && (
        <Callout intent="danger" style={{ marginBottom: 16 }}>
          {error}
        </Callout>
      )}

      {/* Case summary */}
      {results && (
        <>
          <div className="section-heading">Case Summary</div>
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-color)",
              borderRadius: 3,
              padding: 16,
            }}
          >
            <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
              <tbody>
                {[
                  ["Standard", results.standard],
                  ["Bolt", `${boltConfig.designation} — ${boltConfig.grade}`],
                  ["Bolt circle", `${jointConfig.num_bolts}× on PCD ${jointConfig.bolt_circle_diameter_mm} mm`],
                  ["Grip length", `${jointConfig.layers.reduce((s, l) => s + l.thickness_mm, 0).toFixed(1)} mm (${jointConfig.layers.length} layers)`],
                  ["Load cases", `${loadCases.length} case(s)`],
                  ...(results.case_results[0]
                    ? [
                        ["Binding check", results.case_results[0].margins.find((m) => m.binding)?.check_name ?? "—"],
                        [
                          "Min MS",
                          (() => {
                            const b = results.case_results[0].margins.find((m) => m.binding);
                            return b
                              ? `${b.value >= 0 ? "+" : ""}${b.value.toFixed(3)} (${b.status})`
                              : "—";
                          })(),
                        ],
                      ]
                    : []),
                ].map(([k, v]) => (
                  <tr key={k} style={{ borderBottom: "1px solid var(--border-color)" }}>
                    <td style={{ padding: "6px 0", color: "var(--text-muted)", width: "35%" }}>{k}</td>
                    <td className="mono" style={{ padding: "6px 0", color: "var(--text-primary)" }}>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <div className="page-actions">
        <Button minimal icon="arrow-left" onClick={() => setCurrentStep(3)}>
          Results
        </Button>
      </div>

      {/* Hidden file input ref */}
      <input ref={fileInputRef} type="file" accept=".json" style={{ display: "none" }} />
    </div>
  );
}

import { useRef, useState } from "react";
import { FormGroup, NumericInput, Button, InputGroup, Callout, Spinner, Collapse, HTMLSelect } from "@blueprintjs/core";
import { useAppStore, DEFAULT_LOAD_CASE } from "../store/useAppStore";
import type { LoadCase } from "../types";

/** Parse a load-case CSV. Header columns (any order, extras ignored):
 * case_name, axial_force_N, bending_moment_Nm, shear_force_N, torsion_Nm,
 * load_factor, axial_force_min_N, bending_moment_min_Nm, delta_T_C
 * Moments in N·m.
 */
function parseLoadCaseCsv(text: string): LoadCase[] {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length > 0);
  if (lines.length < 2) throw new Error("CSV needs a header row and at least one data row");
  const header = lines[0].split(",").map((h) => h.trim().toLowerCase());
  const col = (name: string) => header.indexOf(name.toLowerCase());
  const num = (cells: string[], idx: number, fallback = 0) => {
    if (idx < 0 || idx >= cells.length || cells[idx].trim() === "") return fallback;
    const v = parseFloat(cells[idx]);
    if (Number.isNaN(v)) throw new Error(`Not a number: "${cells[idx]}"`);
    return v;
  };
  return lines.slice(1).map((line, i) => {
    const c = line.split(",").map((x) => x.trim());
    const nameIdx = col("case_name");
    return {
      ...DEFAULT_LOAD_CASE,
      case_name: nameIdx >= 0 && c[nameIdx] ? c[nameIdx] : `LC${i + 1}`,
      axial_force_N: num(c, col("axial_force_n")),
      bending_moment_Nmm: num(c, col("bending_moment_nm")) * 1000,
      shear_force_N: num(c, col("shear_force_n")),
      torsion_Nmm: num(c, col("torsion_nm")) * 1000,
      load_factor: num(c, col("load_factor"), 1.0),
      axial_force_min_N: num(c, col("axial_force_min_n")),
      bending_moment_min_Nmm: num(c, col("bending_moment_min_nm")) * 1000,
      delta_T_C: num(c, col("delta_t_c")),
    };
  });
}

export function Loading() {
  const {
    loadCases,
    addLoadCase,
    removeLoadCase,
    updateLoadCase,
    setLoadCases,
    runAnalysis,
    isAnalyzing,
    analyzeError,
    setCurrentStep,
    standard,
  } = useAppStore();
  const [openAdvanced, setOpenAdvanced] = useState<Set<number>>(new Set());
  const [csvError, setCsvError] = useState<string | null>(null);
  const csvInputRef = useRef<HTMLInputElement>(null);

  const toggleAdvanced = (i: number) => {
    const next = new Set(openAdvanced);
    if (next.has(i)) next.delete(i); else next.add(i);
    setOpenAdvanced(next);
  };

  const duplicateCase = (i: number) => {
    const copy = { ...loadCases[i], case_name: `${loadCases[i].case_name} copy` };
    setLoadCases([...loadCases.slice(0, i + 1), copy, ...loadCases.slice(i + 1)]);
  };

  const handleCsv = async (file: File) => {
    setCsvError(null);
    try {
      const cases = parseLoadCaseCsv(await file.text());
      if (cases.length === 0) throw new Error("No load cases found in file");
      setLoadCases(cases);
    } catch (e: unknown) {
      setCsvError(e instanceof Error ? e.message : "CSV import failed");
    }
  };

  const handleRunAnalysis = async () => {
    await runAnalysis();
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <div className="section-heading" style={{ marginTop: 0, marginBottom: 4 }}>Load Cases</div>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0 }}>
            Define one or more load cases. All cases are analysed independently
            under the <strong>{standard}</strong> convention (change it in the header).
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Button
            icon="import"
            minimal
            onClick={() => csvInputRef.current?.click()}
            title="CSV columns: case_name, axial_force_N, bending_moment_Nm, shear_force_N, torsion_Nm, load_factor, axial_force_min_N, bending_moment_min_Nm, delta_T_C (moments in N·m)"
          >
            Import CSV
          </Button>
          <input
            ref={csvInputRef}
            type="file"
            accept=".csv,text/csv"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleCsv(f);
              e.target.value = "";
            }}
          />
          <Button icon="plus" minimal intent="primary" onClick={addLoadCase}>
            Add Load Case
          </Button>
        </div>
      </div>

      {csvError && (
        <Callout intent="danger" style={{ marginBottom: 12 }}>
          CSV import: {csvError}
        </Callout>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 16, marginBottom: 24 }}>
        {loadCases.map((lc, i) => (
          <div
            key={i}
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-color)",
              borderRadius: 3,
              padding: 16,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span className="mono" style={{ color: "var(--accent)", fontSize: 13, fontWeight: 600 }}>
                  {String(i + 1).padStart(2, "0")}
                </span>
                <InputGroup
                  value={lc.case_name}
                  onChange={(e) => updateLoadCase(i, { case_name: e.target.value })}
                  style={{ width: 120 }}
                  small
                />
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                <Button
                  icon="duplicate"
                  minimal
                  small
                  onClick={() => duplicateCase(i)}
                  title="Duplicate case"
                />
                {loadCases.length > 1 && (
                  <Button
                    icon="trash"
                    minimal
                    small
                    intent="danger"
                    onClick={() => removeLoadCase(i)}
                  />
                )}
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
              <FormGroup label="Axial force F_A [N]" style={{ marginBottom: 0 }}>
                <NumericInput
                  value={lc.axial_force_N}
                  stepSize={100}
                  majorStepSize={1000}
                  onValueChange={(v) => updateLoadCase(i, { axial_force_N: v })}
                  fill
                />
              </FormGroup>
              <FormGroup label="Bending M_B [N·m]" style={{ marginBottom: 0 }}>
                <NumericInput
                  value={lc.bending_moment_Nmm / 1000}
                  stepSize={1}
                  minorStepSize={0.1}
                  majorStepSize={10}
                  onValueChange={(v) => !Number.isNaN(v) && updateLoadCase(i, { bending_moment_Nmm: Math.round(v * 1000) })}
                  fill
                />
              </FormGroup>
              <FormGroup label="Shear V [N]" style={{ marginBottom: 0 }}>
                <NumericInput
                  value={lc.shear_force_N}
                  stepSize={100}
                  majorStepSize={1000}
                  onValueChange={(v) => updateLoadCase(i, { shear_force_N: v })}
                  fill
                />
              </FormGroup>
              <FormGroup label="Torsion M_T [N·m]" style={{ marginBottom: 0 }}>
                <NumericInput
                  value={lc.torsion_Nmm / 1000}
                  stepSize={1}
                  minorStepSize={0.1}
                  majorStepSize={10}
                  onValueChange={(v) => !Number.isNaN(v) && updateLoadCase(i, { torsion_Nmm: Math.round(v * 1000) })}
                  fill
                />
              </FormGroup>
              <FormGroup label="Load factor γ" style={{ marginBottom: 0 }}>
                <NumericInput
                  value={lc.load_factor}
                  min={0.1}
                  max={10.0}
                  stepSize={0.1}
                  minorStepSize={0.05}
                  majorStepSize={0.5}
                  onValueChange={(v) => updateLoadCase(i, { load_factor: v })}
                  fill
                />
              </FormGroup>
            </div>

            <Button
              minimal
              small
              icon={openAdvanced.has(i) ? "chevron-down" : "chevron-right"}
              onClick={() => toggleAdvanced(i)}
              style={{ marginTop: 10 }}
            >
              Advanced (cycle minimum, thermal, load plane)
            </Button>
            <Collapse isOpen={openAdvanced.has(i)}>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(5, 1fr)",
                  gap: 12,
                  marginTop: 10,
                  paddingTop: 10,
                  borderTop: "1px dashed var(--border-color)",
                }}
              >
                <FormGroup
                  label="Min axial F_A,min [N]"
                  helperText="Cycle minimum (fatigue). 0 = pulsating."
                  style={{ marginBottom: 0 }}
                >
                  <NumericInput
                    value={lc.axial_force_min_N}
                    stepSize={100}
                    majorStepSize={1000}
                    onValueChange={(v) => !Number.isNaN(v) && updateLoadCase(i, { axial_force_min_N: v })}
                    fill
                  />
                </FormGroup>
                <FormGroup label="Min bending M_B,min [N·m]" style={{ marginBottom: 0 }}>
                  <NumericInput
                    value={lc.bending_moment_min_Nmm / 1000}
                    stepSize={1}
                    minorStepSize={0.1}
                    majorStepSize={10}
                    onValueChange={(v) => !Number.isNaN(v) && updateLoadCase(i, { bending_moment_min_Nmm: Math.round(v * 1000) })}
                    fill
                  />
                </FormGroup>
                <FormGroup
                  label="ΔT from assembly [K]"
                  helperText="Thermal preload change via CTE mismatch."
                  style={{ marginBottom: 0 }}
                >
                  <NumericInput
                    value={lc.delta_T_C}
                    min={-300}
                    max={1000}
                    stepSize={5}
                    minorStepSize={1}
                    majorStepSize={25}
                    onValueChange={(v) => !Number.isNaN(v) && updateLoadCase(i, { delta_T_C: v })}
                    fill
                  />
                </FormGroup>
                <FormGroup
                  label="Load plane"
                  helperText="Bolt head → n = 1 for this case."
                  style={{ marginBottom: 0 }}
                >
                  <HTMLSelect
                    value={lc.load_plane}
                    onChange={(e) => updateLoadCase(i, { load_plane: e.target.value as "interface" | "bolt_head" })}
                    options={[
                      { label: "Interface", value: "interface" },
                      { label: "Bolt head / nut", value: "bolt_head" },
                    ]}
                    fill
                  />
                </FormGroup>
              </div>
            </Collapse>
          </div>
        ))}
      </div>

      {analyzeError && (
        <Callout intent="danger" style={{ marginBottom: 16 }}>
          {analyzeError}
        </Callout>
      )}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          paddingTop: 16,
          borderTop: "1px solid var(--border-color)",
        }}
      >
        <Button minimal icon="arrow-left" onClick={() => setCurrentStep(1)}>
          Joint Geometry
        </Button>
        <Button
          intent="primary"
          large
          icon={isAnalyzing ? undefined : "play"}
          onClick={handleRunAnalysis}
          disabled={isAnalyzing}
        >
          {isAnalyzing ? (
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Spinner size={16} />
              Running Analysis…
            </span>
          ) : (
            "Run Full VDI 2230 Analysis"
          )}
        </Button>
      </div>
    </div>
  );
}

import { FormGroup, NumericInput, Button, InputGroup, Callout, Spinner } from "@blueprintjs/core";
import { useAppStore } from "../store/useAppStore";

export function Loading() {
  const {
    loadCases,
    addLoadCase,
    removeLoadCase,
    updateLoadCase,
    runAnalysis,
    isAnalyzing,
    analyzeError,
    setCurrentStep,
    standard,
  } = useAppStore();

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
          <Button icon="plus" minimal intent="primary" onClick={addLoadCase}>
            Add Load Case
          </Button>
        </div>
      </div>

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
                  min={1.0}
                  max={10.0}
                  stepSize={0.1}
                  minorStepSize={0.05}
                  onValueChange={(v) => updateLoadCase(i, { load_factor: v })}
                  fill
                />
              </FormGroup>
            </div>
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

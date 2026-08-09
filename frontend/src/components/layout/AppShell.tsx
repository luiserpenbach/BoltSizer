import { useState } from "react";
import {
  Tabs, Tab, Icon, Button, HTMLSelect, Popover, Dialog, DialogBody,
  Tag, FormGroup, NumericInput, Alert, Classes,
} from "@blueprintjs/core";
import { useAppStore, useResultsStale } from "../../store/useAppStore";
import type { ReactNode } from "react";

export const APP_VERSION = "1.2.0";

const STEPS = [
  { id: 0, label: "Bolt Selection", icon: "wrench" as const },
  { id: 1, label: "Joint Geometry", icon: "social-media" as const },
  { id: 2, label: "Loading", icon: "lightning" as const },
  { id: 3, label: "Results", icon: "chart" as const },
  { id: 4, label: "Report", icon: "document" as const },
];

// Defaults applied when a FoS override is null (mirrors backend ecss module)
const STANDARD_FOS: Record<"VDI" | "ECSS", { y: number; u: number; sep: number; slip: number }> = {
  VDI: { y: 1.0, u: 1.0, sep: 1.0, slip: 1.0 },
  ECSS: { y: 1.1, u: 1.25, sep: 1.2, slip: 1.0 },
};

function FosPanel() {
  const { standard, fos, setFos } = useAppStore();
  const d = STANDARD_FOS[standard];
  const rows: Array<{ key: keyof typeof fos; label: string; def: number }> = [
    { key: "fos_yield", label: "Yield", def: d.y },
    { key: "fos_ultimate", label: "Ultimate", def: d.u },
    { key: "fos_separation", label: "Separation", def: d.sep },
    { key: "fos_slip", label: "Slip", def: d.slip },
  ];
  return (
    <div style={{ padding: 14, width: 300 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>Factors of safety</div>
      <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 0 }}>
        Blank = {standard} default. Applied to every margin as
        MS&nbsp;=&nbsp;allowable/(FoS·applied)&nbsp;−&nbsp;1.
      </p>
      {rows.map((r) => (
        <FormGroup key={r.key} label={`${r.label} (default ${r.def.toFixed(2)})`} style={{ marginBottom: 8 }}>
          <NumericInput
            value={(fos[r.key] as number | null) ?? undefined}
            placeholder={r.def.toFixed(2)}
            min={0.5}
            max={5}
            stepSize={0.05}
            minorStepSize={0.01}
            majorStepSize={0.25}
            onValueChange={(v, str) =>
              setFos({ [r.key]: str === "" || Number.isNaN(v) ? null : v })
            }
            fill
            small
          />
        </FormGroup>
      ))}
      <div className="two-col-equal" style={{ display: "flex", gap: 8 }}>
        <FormGroup label="Installation yield" style={{ flex: 1, marginBottom: 4 }}>
          <NumericInput
            value={fos.fos_yield_installation}
            min={0.5} max={5} stepSize={0.05} minorStepSize={0.01} majorStepSize={0.25}
            onValueChange={(v) => !Number.isNaN(v) && setFos({ fos_yield_installation: v })}
            fill small
          />
        </FormGroup>
        <FormGroup label="Installation ult." style={{ flex: 1, marginBottom: 4 }}>
          <NumericInput
            value={fos.fos_ultimate_installation}
            min={0.5} max={5} stepSize={0.05} minorStepSize={0.01} majorStepSize={0.25}
            onValueChange={(v) => !Number.isNaN(v) && setFos({ fos_ultimate_installation: v })}
            fill small
          />
        </FormGroup>
      </div>
      <Button
        small minimal icon="reset"
        onClick={() =>
          setFos({
            fos_yield: null, fos_ultimate: null, fos_separation: null, fos_slip: null,
            fos_yield_installation: 1.0, fos_ultimate_installation: 1.0,
          })
        }
      >
        Reset to {standard} defaults
      </Button>
    </div>
  );
}

interface Props {
  children: ReactNode;
}

export function AppShell({ children }: Props) {
  const {
    currentStep, setCurrentStep, results, standard, setStandard,
    isAnalyzing, runAnalysis, resetAll, fos,
  } = useAppStore();
  const stale = useResultsStale();
  const [aboutOpen, setAboutOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);

  const warningCount = results
    ? results.case_results.reduce((n, c) => n + c.warnings.length, 0)
    : 0;
  const anyFail = results
    ? results.case_results.some((c) => c.margins.some((m) => m.status === "FAIL"))
    : false;

  const isStepEnabled = (id: number) => {
    if (id <= 2) return true;
    return results !== null;
  };

  const fosSummary = (() => {
    const d = STANDARD_FOS[standard];
    const y = fos.fos_yield ?? d.y;
    const u = fos.fos_ultimate ?? d.u;
    const sep = fos.fos_separation ?? d.sep;
    return `FoS ${y.toFixed(2)}/${u.toFixed(2)}/${sep.toFixed(2)}`;
  })();

  const handleRun = async () => {
    await runAnalysis();
    if (useAppStore.getState().results) setCurrentStep(3);
  };

  return (
    <div className="app-shell bp5-dark">
      {/* Top bar */}
      <div className="app-topbar">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Icon icon="wrench" color="var(--accent)" size={16} />
          <span className="app-brand">
            Bolt<span className="brand-accent">Sizer</span>
          </span>
        </div>
        <span className="app-title" style={{ marginLeft: 8 }}>
          Bolted Joint Analysis
        </span>
        <div style={{ flex: 1 }} />

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <HTMLSelect
            value={standard}
            onChange={(e) => setStandard(e.target.value as "VDI" | "ECSS")}
            options={[
              { label: "VDI 2230", value: "VDI" },
              { label: "ECSS-E-HB-32-23", value: "ECSS" },
            ]}
            minimal
          />
          <Popover content={<FosPanel />} placement="bottom-end">
            <Button minimal small icon="shield" text={fosSummary} />
          </Popover>

          {stale && (
            <Tag intent="warning" minimal icon="outdated">
              inputs changed
            </Tag>
          )}
          <Button
            intent="primary"
            small
            icon="play"
            loading={isAnalyzing}
            onClick={handleRun}
            data-testid="global-run"
          >
            Run
          </Button>

          <Button minimal small icon="info-sign" onClick={() => setAboutOpen(true)} aria-label="About" />
          <Button minimal small icon="reset" onClick={() => setResetOpen(true)} aria-label="Reset all inputs" />
        </div>
      </div>

      {/* Step navigation */}
      <div className="step-nav">
        <Tabs
          id="step-tabs"
          selectedTabId={currentStep}
          onChange={(id) => {
            const n = id as number;
            if (isStepEnabled(n)) setCurrentStep(n);
          }}
          animate
          renderActiveTabPanelOnly={false}
        >
          {STEPS.map((s) => (
            <Tab
              key={s.id}
              id={s.id}
              disabled={!isStepEnabled(s.id)}
              title={
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Icon icon={s.icon} size={12} />
                  {s.label}
                  {s.id === 3 && warningCount > 0 && (
                    <Tag round minimal intent={anyFail ? "danger" : "warning"} style={{ marginLeft: 2 }}>
                      {warningCount}
                    </Tag>
                  )}
                </span>
              }
            />
          ))}
        </Tabs>
      </div>

      {/* Page content */}
      <div className="main-content">{children}</div>

      {/* About dialog */}
      <Dialog
        isOpen={aboutOpen}
        onClose={() => setAboutOpen(false)}
        title={`BoltSizer v${APP_VERSION}`}
        className="bp5-dark"
      >
        <DialogBody>
          <p style={{ marginTop: 0 }}>
            Bolted-joint analysis per <strong>VDI 2230 Part 1 (2014)</strong> with
            optional <strong>ECSS-E-HB-32-23A</strong> conventions and factors of safety.
          </p>
          <p>
            <Tag intent="success" icon="tick" minimal>Engine validated</Tag>{" "}
            Cross-checked against a SpaceBolt v2.2 reference report: preload chain,
            embedding loss and installation stress agree to ≤1%; remaining margin
            differences are documented conservative conventions.
          </p>
          <ul style={{ fontSize: 13 }}>
            <li><code>AUDIT.md</code> — engine correctness audit &amp; fix log</li>
            <li><code>VALIDATION.md</code> — SpaceBolt cross-validation record</li>
            <li><code>tests/</code> — 97 tests incl. reference validation suite</li>
          </ul>
          <p className={Classes.TEXT_MUTED} style={{ fontSize: 12 }}>
            Results are engineering estimates. Verify against applicable project
            standards before flight/production use.
          </p>
        </DialogBody>
      </Dialog>

      {/* Reset confirmation */}
      <Alert
        isOpen={resetOpen}
        className="bp5-dark"
        cancelButtonText="Cancel"
        confirmButtonText="Reset everything"
        intent="danger"
        icon="reset"
        onCancel={() => setResetOpen(false)}
        onConfirm={() => {
          resetAll();
          setResetOpen(false);
        }}
      >
        Reset all inputs, load cases, factors of safety and results to defaults?
        This clears the saved session as well.
      </Alert>
    </div>
  );
}

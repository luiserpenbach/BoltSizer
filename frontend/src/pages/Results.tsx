import { useState } from "react";
import { Tabs, Tab, Button, Callout } from "@blueprintjs/core";
import { StatusTag } from "../components/shared/StatusTag";
import { CalcStepCard } from "../components/shared/CalcStepCard";
import { MarginBar } from "../components/charts/MarginBar";
import { ForceWaterfall } from "../components/charts/ForceWaterfall";
import { BoltCircleViz } from "../components/charts/BoltCircleViz";
import { useAppStore, useResultsStale } from "../store/useAppStore";
import { TorqueWindowPanel } from "../components/TorqueWindowPanel";
import { SensitivityPanel } from "../components/SensitivityPanel";
import type { BoltResults } from "../types";

function CaseResults({ caseResult }: { caseResult: BoltResults }) {
  const [showCalcChain, setShowCalcChain] = useState(false);
  const { jointConfig } = useAppStore();
  const binding = caseResult.margins.find((m) => m.binding);

  return (
    <div>
      {/* Summary cards */}
      <div className="summary-cards">
        <div
          className="summary-card"
          style={{
            borderColor: binding
              ? binding.status === "PASS"
                ? "var(--pass-color)"
                : binding.status === "FAIL"
                ? "var(--fail-color)"
                : "var(--warn-color)"
              : undefined,
          }}
        >
          <div className="metric-label">Binding Margin (min MS)</div>
          <div
            className="metric-value mono"
            style={{
              color: binding
                ? binding.status === "PASS"
                  ? "var(--pass-color)"
                  : binding.status === "FAIL"
                  ? "var(--fail-color)"
                  : "var(--warn-color)"
                : undefined,
            }}
          >
            {binding ? (binding.value >= 0 ? "+" : "") + binding.value.toFixed(3) : "—"}
          </div>
          <div className="metric-sub">{binding?.check_name}</div>
        </div>
        <div className="summary-card">
          <div className="metric-label">Min Working Preload</div>
          <div className="metric-value mono">
            {caseResult.preload.F_preload_min.toLocaleString(undefined, { maximumFractionDigits: 0 })} N
          </div>
          <div className="metric-sub">After all preload losses</div>
        </div>
        <div className="summary-card">
          <div className="metric-label">Max Bolt Load</div>
          <div className="metric-value mono">
            {caseResult.bolt_load_max.toLocaleString(undefined, { maximumFractionDigits: 0 })} N
          </div>
          <div className="metric-sub">Under operating conditions</div>
        </div>
        <div className="summary-card">
          <div className="metric-label">Force Ratio φ_n</div>
          <div className="metric-value mono">{caseResult.stiffness.phi_n.toFixed(4)}</div>
          <div className="metric-sub">Bolt load fraction</div>
        </div>
        <div className="summary-card">
          <div className="metric-label">Min Clamping Force</div>
          <div className="metric-value mono">
            {caseResult.F_clamp_min.toLocaleString(undefined, { maximumFractionDigits: 0 })} N
          </div>
          <div className="metric-sub">Per bolt, critical bolt</div>
        </div>
      </div>

      {/* Warnings */}
      {caseResult.warnings.length > 0 && (
        <div className="warning-list" style={{ marginBottom: 20 }}>
          {caseResult.warnings.map((w, i) => (
            <div key={i} className="warning-item">{w}</div>
          ))}
        </div>
      )}

      {/* Two-column: table + chart */}
      <div className="two-col" style={{ marginBottom: 20 }}>
        <div>
          <div className="section-heading">Margins of Safety</div>
          <table className="margins-table">
            <thead>
              <tr>
                <th>Check</th>
                <th>MS</th>
                <th>Status</th>
                <th>Allowable</th>
                <th>Applied</th>
                <th>Unit</th>
              </tr>
            </thead>
            <tbody>
              {caseResult.margins.map((m, i) => (
                <tr key={i} className={m.binding ? "binding-row" : ""}>
                  <td>
                    {m.check_name}
                    {m.binding && (
                      <span
                        className="mono"
                        style={{ fontSize: 10, color: "var(--accent)", marginLeft: 6 }}
                      >
                        ▲ BINDING
                      </span>
                    )}
                  </td>
                  <td>
                    <span className={`ms-value ${m.status.toLowerCase()}`}>
                      {m.value >= 0 ? "+" : ""}{m.value.toFixed(3)}
                    </span>
                  </td>
                  <td>
                    <StatusTag status={m.status} />
                  </td>
                  <td className="mono" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                    {m.allowable.toFixed(1)}
                  </td>
                  <td className="mono" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                    {m.applied.toFixed(1)}
                  </td>
                  <td style={{ fontSize: 11, color: "var(--text-muted)" }}>{m.unit}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <div className="section-heading">Margin Visualization</div>
          <MarginBar margins={caseResult.margins} />

          <div className="section-heading">Bolt Circle</div>
          <BoltCircleViz
            numBolts={caseResult.load_dist.bolt_angles_deg.length}
            pcd={jointConfig.bolt_circle_diameter_mm}
            criticalBoltIndex={caseResult.load_dist.critical_bolt_index}
            positions={
              jointConfig.pattern !== "circle"
                ? caseResult.load_dist.bolt_positions
                : undefined
            }
          />
        </div>
      </div>

      {/* Preload waterfall */}
      <div className="section-heading">Preload Budget</div>
      <ForceWaterfall preload={caseResult.preload} />

      {/* Calculation chain */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginTop: 24,
        }}
      >
        <div className="section-heading" style={{ marginTop: 0, marginBottom: 0 }}>
          Calculation Chain
        </div>
        <Button minimal small onClick={() => setShowCalcChain(!showCalcChain)}>
          {showCalcChain ? "Collapse" : "Expand"} all steps
        </Button>
      </div>
      <div style={{ marginTop: 8 }}>
        {showCalcChain
          ? caseResult.calc_steps.map((step, i) => (
              <CalcStepCard key={i} step={step} index={i} />
            ))
          : caseResult.calc_steps.slice(0, 3).map((step, i) => (
              <CalcStepCard key={i} step={step} index={i} />
            ))}
        {!showCalcChain && caseResult.calc_steps.length > 3 && (
          <Button minimal small onClick={() => setShowCalcChain(true)} style={{ marginTop: 4 }}>
            Show {caseResult.calc_steps.length - 3} more steps…
          </Button>
        )}
      </div>

      {/* Individual margin explanations */}
      <div className="section-heading">Check Details</div>
      {caseResult.margins.map((m, i) => (
        <div
          key={i}
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-color)",
            borderRadius: 3,
            padding: "10px 14px",
            marginBottom: 8,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <StatusTag status={m.status} />
            <span style={{ fontSize: 13, fontWeight: 500 }}>{m.check_name}</span>
            <span className="mono" style={{ fontSize: 12, color: m.status === "PASS" ? "var(--pass-color)" : m.status === "FAIL" ? "var(--fail-color)" : "var(--warn-color)" }}>
              MS = {m.value >= 0 ? "+" : ""}{m.value.toFixed(3)}
            </span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{m.explanation}</div>
        </div>
      ))}
    </div>
  );
}

function CaseMatrix({ cases }: { cases: BoltResults[] }) {
  // Union of check names, keeping first-case order
  const checks: string[] = [];
  cases.forEach((c) =>
    c.margins.forEach((m) => {
      if (!checks.includes(m.check_name)) checks.push(m.check_name);
    })
  );
  const cell = (c: BoltResults, name: string) =>
    c.margins.find((m) => m.check_name === name);

  return (
    <div style={{ marginBottom: 24 }}>
      <div className="section-heading" style={{ marginTop: 0 }}>
        Case Comparison — governing case per check
      </div>
      <div style={{ overflowX: "auto" }}>
        <table className="margins-table" style={{ minWidth: 480 }}>
          <thead>
            <tr>
              <th>Check</th>
              {cases.map((c) => (
                <th key={c.case_name} className="mono">{c.case_name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {checks.map((name) => {
              const values = cases.map((c) => cell(c, name)?.value ?? Infinity);
              const governing = Math.min(...values);
              return (
                <tr key={name}>
                  <td>{name}</td>
                  {cases.map((c, i) => {
                    const m = cell(c, name);
                    if (!m) return <td key={i} className="mono">—</td>;
                    const isGov = m.value === governing && Number.isFinite(governing);
                    return (
                      <td
                        key={i}
                        className={`mono ms-value ${m.status.toLowerCase()}`}
                        style={{
                          fontWeight: isGov ? 700 : 400,
                          textDecoration: isGov ? "underline" : "none",
                        }}
                        title={isGov ? "Governing case for this check" : undefined}
                      >
                        {m.value === Infinity || m.value > 1e8
                          ? "∞"
                          : `${m.value >= 0 ? "+" : ""}${m.value.toFixed(3)}`}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function Results() {
  const { results, setCurrentStep, runAnalysis, isAnalyzing } = useAppStore();
  const stale = useResultsStale();

  if (!results) {
    return (
      <Callout intent="warning">
        No analysis results yet. Go to the Loading page and run the analysis.
        <br />
        <Button
          minimal
          intent="primary"
          style={{ marginTop: 8 }}
          onClick={() => setCurrentStep(2)}
        >
          Go to Loading
        </Button>
      </Callout>
    );
  }

  const { case_results } = results;

  return (
    <div>
      {stale && (
        <Callout intent="warning" icon="outdated" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <span>
              Inputs have changed since this analysis was run — the results below
              may not match the current configuration.
            </span>
            <Button small intent="warning" icon="refresh" loading={isAnalyzing} onClick={() => runAnalysis()}>
              Re-run analysis
            </Button>
          </div>
        </Callout>
      )}
      {case_results.length > 1 && <CaseMatrix cases={case_results} />}
      {case_results.length === 1 ? (
        <CaseResults caseResult={case_results[0]} />
      ) : (
        <Tabs id="results-tabs" animate renderActiveTabPanelOnly>
          {case_results.map((cr, i) => (
            <Tab
              key={i}
              id={i}
              title={
                <span>
                  {cr.case_name}{" "}
                  {cr.margins.some((m) => m.status === "FAIL") ? (
                    <span style={{ color: "var(--fail-color)" }}>●</span>
                  ) : cr.margins.some((m) => m.status === "WARNING") ? (
                    <span style={{ color: "var(--warn-color)" }}>●</span>
                  ) : (
                    <span style={{ color: "var(--pass-color)" }}>●</span>
                  )}
                </span>
              }
              panel={<CaseResults caseResult={cr} />}
            />
          ))}
        </Tabs>
      )}

      <TorqueWindowPanel />
      <SensitivityPanel />

      <div className="page-actions">
        <Button minimal icon="arrow-left" onClick={() => setCurrentStep(2)}>Loading</Button>
        <Button intent="primary" rightIcon="arrow-right" onClick={() => setCurrentStep(4)}>
          Report
        </Button>
      </div>
    </div>
  );
}

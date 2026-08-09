import { useState } from "react";
import { Button, Callout, Spinner } from "@blueprintjs/core";
import { useAppStore } from "../store/useAppStore";
import { buildAnalyzeReq, fetchSensitivity } from "../api/client";
import type { SensitivityResult } from "../api/client";

/** One-at-a-time sensitivity tornado of the worst margin. */
export function SensitivityPanel() {
  const { boltConfig, jointConfig, loadCases, standard, fos } = useAppStore();
  const [data, setData] = useState<SensitivityResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const compute = async () => {
    setLoading(true);
    setError(null);
    try {
      const req = buildAnalyzeReq(boltConfig, jointConfig, loadCases, standard, fos);
      setData(await fetchSensitivity(req));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Sensitivity sweep failed");
    } finally {
      setLoading(false);
    }
  };

  // Chart scale across all values incl. baseline
  const values = data
    ? [data.baseline_ms, ...data.params.flatMap((p) => [p.low_ms, p.high_ms])]
    : [0];
  const vMin = Math.min(...values, 0);
  const vMax = Math.max(...values, 0);
  const span = Math.max(vMax - vMin, 1e-6);
  const pct = (v: number) => ((v - vMin) / span) * 100;

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div className="section-heading" style={{ margin: 0 }}>Sensitivity (worst margin)</div>
        <Button small icon="comparison" onClick={compute} loading={loading}>
          {data ? "Recompute" : "Compute sensitivity"}
        </Button>
      </div>
      <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "6px 0 12px" }}>
        One-at-a-time perturbations of the key inputs, ranked by influence on the
        worst margin. Wide bars = the parameters your margin actually depends on.
      </p>

      {error && <Callout intent="danger" style={{ marginBottom: 12 }}>{error}</Callout>}
      {loading && !data && <Spinner size={24} />}

      {data && (
        <div style={{ maxWidth: 720 }}>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>
            Baseline worst MS:{" "}
            <span className={`mono ms-value ${data.baseline_ms >= 0 ? "pass" : "fail"}`}>
              {data.baseline_ms >= 0 ? "+" : ""}{data.baseline_ms.toFixed(3)}
            </span>
          </div>
          {data.params.map((p) => {
            const lo = Math.min(p.low_ms, p.high_ms);
            const hi = Math.max(p.low_ms, p.high_ms);
            return (
              <div key={p.name} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                <div style={{ width: 190, fontSize: 12, color: "var(--text-secondary)", textAlign: "right" }}>
                  {p.name}
                </div>
                <div style={{ flex: 1, position: "relative", height: 18, background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: 2 }}>
                  {/* zero line */}
                  <div style={{ position: "absolute", left: `${pct(0)}%`, top: 0, bottom: 0, width: 1, background: "var(--fail-color)", opacity: 0.7 }} />
                  {/* baseline marker */}
                  <div style={{ position: "absolute", left: `${pct(data.baseline_ms)}%`, top: 0, bottom: 0, width: 2, background: "var(--accent)" }} />
                  {/* swing bar */}
                  <div
                    style={{
                      position: "absolute",
                      left: `${pct(lo)}%`,
                      width: `${Math.max(pct(hi) - pct(lo), 0.5)}%`,
                      top: 3,
                      bottom: 3,
                      background: lo < 0 ? "rgba(205,66,70,0.45)" : "rgba(35,171,110,0.45)",
                      borderRadius: 2,
                    }}
                    title={`${p.low_ms.toFixed(3)} … ${p.high_ms.toFixed(3)}`}
                  />
                </div>
                <div className="mono" style={{ width: 130, fontSize: 11, color: "var(--text-muted)" }}>
                  {p.low_ms >= 0 ? "+" : ""}{p.low_ms.toFixed(2)} … {p.high_ms >= 0 ? "+" : ""}{p.high_ms.toFixed(2)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

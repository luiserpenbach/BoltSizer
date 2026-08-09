import { useState } from "react";
import { Button, Callout, Spinner } from "@blueprintjs/core";
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ReferenceArea, ResponsiveContainer,
} from "recharts";
import { useAppStore } from "../store/useAppStore";
import { buildAnalyzeReq, fetchTorqueWindow } from "../api/client";
import type { TorqueWindowResult } from "../api/client";

/** Torque-window finder: sweeps M_A, shades the allowable band, and can
 * apply the recommended torque back to the bolt configuration. */
export function TorqueWindowPanel() {
  const { boltConfig, jointConfig, loadCases, standard, fos, setBoltConfig, setCurrentStep } =
    useAppStore();
  const [data, setData] = useState<TorqueWindowResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const compute = async () => {
    setLoading(true);
    setError(null);
    try {
      const req = buildAnalyzeReq(boltConfig, jointConfig, loadCases, standard, fos);
      setData(await fetchTorqueWindow(req));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Torque sweep failed");
    } finally {
      setLoading(false);
    }
  };

  const chartData = data?.points.map((p) => ({
    torque_Nm: p.torque / 1000,
    min_ms: Math.max(-1, Math.min(p.min_ms, 3)), // clamp for readability
    governing: p.governing,
  }));

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div className="section-heading" style={{ margin: 0 }}>Torque Window</div>
        <Button small icon="calculator" onClick={compute} loading={loading}>
          {data ? "Recompute" : "Compute torque window"}
        </Button>
      </div>
      <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "6px 0 12px" }}>
        Sweeps the assembly torque and evaluates every margin (worst load case).
        The floor of the band is set by minimum-preload checks (separation, slip),
        the ceiling by maximum-preload checks (assembly yield, surface pressure).
      </p>

      {error && <Callout intent="danger" style={{ marginBottom: 12 }}>{error}</Callout>}
      {loading && !data && <Spinner size={24} />}

      {data && (
        <>
          {data.window && data.recommended ? (
            <Callout intent="success" icon="endorsed" style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <span>
                  Allowable torque{" "}
                  <strong className="mono">
                    {(data.window.t_lo / 1000).toFixed(1)} – {(data.window.t_hi / 1000).toFixed(1)} N·m
                  </strong>
                  {" · "}recommend{" "}
                  <strong className="mono">{(data.recommended.torque / 1000).toFixed(1)} N·m</strong>
                  {" "}(min MS {data.recommended.min_ms >= 0 ? "+" : ""}
                  {data.recommended.min_ms.toFixed(3)}, governed by {data.recommended.governing})
                </span>
                <Button
                  small
                  intent="success"
                  icon="tick"
                  onClick={() => {
                    setBoltConfig({
                      assembly_torque_Nmm: Math.round(data.recommended!.torque / 100) * 100,
                      use_target_preload: false,
                    });
                    setCurrentStep(0);
                  }}
                >
                  Apply recommended torque
                </Button>
              </div>
            </Callout>
          ) : (
            <Callout intent="danger" icon="cross" style={{ marginBottom: 12 }}>
              No torque satisfies all checks for this joint — the strongest point of
              the sweep still fails. Consider a larger bolt, higher-strength grade,
              more bolts, or revisiting the loads.
            </Callout>
          )}

          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={chartData} margin={{ top: 8, right: 24, left: 8, bottom: 20 }}>
              <CartesianGrid stroke="#383e47" vertical={false} />
              <XAxis
                dataKey="torque_Nm"
                type="number"
                domain={["dataMin", "dataMax"]}
                tick={{ fill: "#abb3bf", fontSize: 10 }}
                tickFormatter={(v: number) => v.toFixed(0)}
                label={{ value: "Assembly torque M_A [N·m]", position: "insideBottom", offset: -12, fill: "#abb3bf", fontSize: 11 }}
              />
              <YAxis
                tick={{ fill: "#abb3bf", fontSize: 10, fontFamily: "monospace" }}
                label={{ value: "min MS", angle: -90, position: "insideLeft", fill: "#abb3bf", fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{ background: "#2f343c", border: "1px solid #383e47", fontSize: 12 }}
                formatter={(value) => [Number(value).toFixed(3), "min MS"]}
                labelFormatter={(v) => {
                  const num = Number(v);
                  const pt = chartData?.find((p) => p.torque_Nm === num);
                  return `${num.toFixed(1)} N·m — governed by ${pt?.governing ?? ""}`;
                }}
              />
              {data.window && (
                <ReferenceArea
                  x1={data.window.t_lo / 1000}
                  x2={data.window.t_hi / 1000}
                  fill="#238C2C"
                  fillOpacity={0.15}
                />
              )}
              <ReferenceLine y={0} stroke="#cd4246" strokeDasharray="4 3" />
              {data.recommended && (
                <ReferenceLine
                  x={data.recommended.torque / 1000}
                  stroke="#2d72d2"
                  strokeDasharray="5 3"
                  label={{ value: "recommended", fill: "#2d72d2", fontSize: 10, position: "top" }}
                />
              )}
              <Line
                type="monotone"
                dataKey="min_ms"
                stroke="#f6f7f9"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}

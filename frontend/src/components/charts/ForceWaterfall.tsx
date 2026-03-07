import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
} from "recharts";
import type { PreloadResult } from "../../types";

interface Props {
  preload: PreloadResult;
}

export function ForceWaterfall({ preload }: Props) {
  // Build waterfall data
  const bars = [
    {
      name: "F_M_max",
      value: preload.F_M_max,
      color: "#2d72d2",
      label: "Assembly\nPreload Max",
    },
    {
      name: "Scatter",
      value: -(preload.F_M_max - preload.F_M_min),
      color: "#c87619",
      label: "Scatter\nLoss",
    },
    {
      name: "Embedding",
      value: -preload.F_Z,
      color: "#cd4246",
      label: "Embedding\nLoss",
    },
    {
      name: "F_V_min",
      value: preload.F_preload_min,
      color: "#23ab6e",
      label: "Min Working\nPreload",
    },
  ];

  const CustomTooltip = ({ active, payload, label }: {active?: boolean; payload?: {payload: {value: number; color: string}}[]; label?: string}) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div
        style={{
          background: "#2f343c",
          border: "1px solid #383e47",
          borderRadius: 3,
          padding: "8px 12px",
          fontSize: 12,
        }}
      >
        <div style={{ color: "#f6f7f9", marginBottom: 4 }}>{label}</div>
        <div style={{ color: d.color, fontFamily: "monospace" }}>
          {d.value >= 0 ? "+" : ""}{d.value.toFixed(0)} N
        </div>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={bars} margin={{ top: 8, right: 20, left: 10, bottom: 8 }}>
        <CartesianGrid vertical={false} stroke="#383e47" />
        <XAxis
          dataKey="label"
          tick={{ fill: "#abb3bf", fontSize: 10 }}
          axisLine={{ stroke: "#383e47" }}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "#abb3bf", fontSize: 11, fontFamily: "monospace" }}
          tickFormatter={(v) => `${(v / 1000).toFixed(1)}kN`}
          axisLine={{ stroke: "#383e47" }}
          tickLine={false}
        />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="value" radius={[2, 2, 0, 0]}>
          {bars.map((b, i) => (
            <Cell key={i} fill={b.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

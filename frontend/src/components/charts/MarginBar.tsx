import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Cell,
  ResponsiveContainer,
} from "recharts";
import type { MarginOfSafety } from "../../types";

interface Props {
  margins: MarginOfSafety[];
}

const PASS_COLOR = "#23ab6e";
const FAIL_COLOR = "#cd4246";
const WARN_COLOR = "#c87619";

export function MarginBar({ margins }: Props) {
  const data = margins.map((m) => ({
    name: m.check_name,
    ms: parseFloat(Math.max(m.value, -1).toFixed(3)),
    status: m.status,
    binding: m.binding,
  }));

  const getColor = (status: string) => {
    if (status === "PASS") return PASS_COLOR;
    if (status === "FAIL") return FAIL_COLOR;
    return WARN_COLOR;
  };

  const CustomTooltip = ({ active, payload, label }: {active?: boolean; payload?: {payload: {ms: number; status: string}}[]; label?: string}) => {
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
        <div style={{ color: getColor(d.status), fontFamily: "monospace" }}>
          MS = {d.ms >= 0 ? "+" : ""}{d.ms.toFixed(3)}
        </div>
        <div style={{ color: "#abb3bf" }}>{d.status}</div>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 4, right: 60, left: 10, bottom: 4 }}
      >
        <CartesianGrid horizontal={false} stroke="#383e47" />
        <XAxis
          type="number"
          domain={["auto", "auto"]}
          tickFormatter={(v) => v.toFixed(2)}
          tick={{ fill: "#abb3bf", fontSize: 11, fontFamily: "monospace" }}
          axisLine={{ stroke: "#383e47" }}
          tickLine={{ stroke: "#383e47" }}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={130}
          tick={{ fill: "#abb3bf", fontSize: 11 }}
          axisLine={{ stroke: "#383e47" }}
          tickLine={false}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine x={0} stroke="#abb3bf" strokeWidth={1} />
        <Bar dataKey="ms" radius={[0, 2, 2, 0]} label={{ position: "right", fill: "#abb3bf", fontSize: 11, fontFamily: "monospace", formatter: (v: unknown) => { const n = v as number; return n >= 0 ? `+${n.toFixed(3)}` : n.toFixed(3); } }}>
          {data.map((entry, i) => (
            <Cell key={i} fill={getColor(entry.status)} opacity={entry.binding ? 1 : 0.65} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

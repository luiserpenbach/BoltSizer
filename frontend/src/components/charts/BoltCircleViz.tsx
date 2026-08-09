interface Props {
  numBolts: number;
  pcd: number;
  criticalBoltIndex?: number;
  /** Explicit XY positions [mm] about the centroid (rectangle/custom
   * patterns). When given, they override the circle layout. */
  positions?: [number, number][];
  label?: string;
}

export function BoltCircleViz({ numBolts, pcd, criticalBoltIndex, positions, label }: Props) {
  const svgSize = 200;
  const cx = svgSize / 2;
  const cy = svgSize / 2;
  const radius = 70;
  const boltR = 7;

  let bolts: { x: number; y: number; isCritical: boolean }[];
  let footer: string;

  if (positions && positions.length > 0) {
    // Scale arbitrary positions to fit the frame (y up → SVG y down)
    const maxExtent = Math.max(1, ...positions.map(([x, y]) => Math.max(Math.abs(x), Math.abs(y))));
    const scale = radius / maxExtent;
    bolts = positions.map(([x, y], i) => ({
      x: cx + x * scale,
      y: cy - y * scale,
      isCritical: i === criticalBoltIndex,
    }));
    footer = label ?? `${positions.length} bolts`;
  } else {
    bolts = Array.from({ length: numBolts }, (_, i) => {
      const angle = (2 * Math.PI * i) / numBolts - Math.PI / 2;
      return {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
        isCritical: i === criticalBoltIndex,
      };
    });
    footer = label ?? `PCD ${pcd.toFixed(0)} mm | ${numBolts} bolts`;
  }

  return (
    <svg
      width={svgSize}
      height={svgSize}
      viewBox={`0 0 ${svgSize} ${svgSize}`}
      style={{ display: "block", margin: "0 auto" }}
    >
      {/* Background */}
      <circle
        cx={cx}
        cy={cy}
        r={radius + boltR + 8}
        fill="none"
        stroke="#383e47"
        strokeWidth={1}
        strokeDasharray="4 4"
      />
      {!positions && (
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke="#404854"
          strokeWidth={1}
          strokeDasharray="2 4"
        />
      )}
      {/* Center cross */}
      <line x1={cx - 10} y1={cy} x2={cx + 10} y2={cy} stroke="#404854" strokeWidth={1} />
      <line x1={cx} y1={cy - 10} x2={cx} y2={cy + 10} stroke="#404854" strokeWidth={1} />
      {/* Bolts */}
      {bolts.map((b, i) => (
        <g key={i}>
          <circle
            cx={b.x}
            cy={b.y}
            r={boltR}
            fill={b.isCritical ? "rgba(205,66,70,0.2)" : "rgba(45,114,210,0.15)"}
            stroke={b.isCritical ? "#cd4246" : "#2d72d2"}
            strokeWidth={1.5}
          />
          <text
            x={b.x}
            y={b.y + 4}
            textAnchor="middle"
            fontSize={8}
            fill={b.isCritical ? "#cd4246" : "#abb3bf"}
            fontFamily="monospace"
          >
            {i + 1}
          </text>
        </g>
      ))}
      <text x={cx} y={svgSize - 6} textAnchor="middle" fontSize={9} fill="#5f6b7c" fontFamily="monospace">
        {footer}
      </text>
    </svg>
  );
}

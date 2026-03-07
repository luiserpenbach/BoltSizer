interface Props {
  numBolts: number;
  pcd: number;
  criticalBoltIndex?: number;
}

export function BoltCircleViz({ numBolts, pcd, criticalBoltIndex }: Props) {
  const svgSize = 200;
  const cx = svgSize / 2;
  const cy = svgSize / 2;
  const radius = 70;
  const boltR = 7;

  const bolts = Array.from({ length: numBolts }, (_, i) => {
    const angle = (2 * Math.PI * i) / numBolts - Math.PI / 2;
    return {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
      isCritical: i === criticalBoltIndex,
    };
  });

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
      {/* PCD circle */}
      <circle
        cx={cx}
        cy={cy}
        r={radius}
        fill="none"
        stroke="#404854"
        strokeWidth={1}
        strokeDasharray="2 4"
      />
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
      {/* PCD label */}
      <text x={cx} y={svgSize - 6} textAnchor="middle" fontSize={9} fill="#5f6b7c" fontFamily="monospace">
        PCD {pcd.toFixed(0)} mm | {numBolts} bolts
      </text>
    </svg>
  );
}

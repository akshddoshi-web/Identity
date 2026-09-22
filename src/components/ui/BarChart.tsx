interface Point {
  label: string;
  value: number;
}

interface Props {
  data: Point[];
  color: string;
  width?: number;
  height?: number;
}

export function BarChart({ data, color, width = 560, height = 140 }: Props) {
  const max = Math.max(...data.map((d) => d.value));
  const bw = width / data.length;

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height + 24}`} style={{ maxWidth: width }}>
      {data.map((d, i) => {
        const bh = (d.value / max) * height;
        const isLast = i === data.length - 1;
        return (
          <g key={d.label}>
            <rect
              x={i * bw + bw * 0.2}
              y={height - bh}
              width={bw * 0.6}
              height={bh}
              rx={4}
              fill={color}
              opacity={isLast ? 1 : 0.55}
            />
            <text
              x={i * bw + bw * 0.5}
              y={height + 18}
              textAnchor="middle"
              fontSize={10}
              fill="var(--sub)"
            >
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

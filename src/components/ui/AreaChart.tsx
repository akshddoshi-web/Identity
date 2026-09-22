import { useId } from "react";

interface Props {
  data: number[];
  color: string;
  width?: number;
  height?: number;
}

export function AreaChart({ data, color, width = 760, height = 220 }: Props) {
  const gid = "area-" + useId().replace(/[:]/g, "");
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pad = 10;

  const points = data.map((v, i): [number, number] => [
    (i / (data.length - 1)) * width,
    height - ((v - min) / range) * (height - pad * 2) - pad,
  ]);
  const line = points.map((p) => p.join(",")).join(" ");
  const area = `0,${height} ${line} ${width},${height}`;

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ maxWidth: width, display: "block" }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.28} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#${gid})`} />
      <polyline points={line} fill="none" stroke={color} strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

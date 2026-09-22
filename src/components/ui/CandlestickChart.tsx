import type { OHLCPoint } from "@/types/stocks";

interface Props {
  data: OHLCPoint[];
  width?: number;
  height?: number;
}

export function CandlestickChart({ data, width = 760, height = 220 }: Props) {
  const highs = data.map((d) => d.high);
  const lows = data.map((d) => d.low);
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const range = max - min || 1;
  const bw = width / data.length;

  const y = (v: number) => height - ((v - min) / range) * height;

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ maxWidth: width, display: "block" }}>
      {data.map((d, i) => {
        const up = d.close >= d.open;
        const color = up ? "var(--pos)" : "var(--neg)";
        const cx = i * bw + bw / 2;
        const bodyTop = y(Math.max(d.open, d.close));
        const bodyBottom = y(Math.min(d.open, d.close));
        const bodyHeight = Math.max(bodyBottom - bodyTop, 1);
        const bodyWidth = Math.max(bw * 0.62, 1);

        return (
          <g key={d.date}>
            <line x1={cx} x2={cx} y1={y(d.high)} y2={y(d.low)} stroke={color} strokeWidth={1} />
            <rect x={cx - bodyWidth / 2} y={bodyTop} width={bodyWidth} height={bodyHeight} fill={color} />
          </g>
        );
      })}
    </svg>
  );
}

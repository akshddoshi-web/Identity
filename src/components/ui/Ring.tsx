interface Props {
  current: number;
  goal: number;
  color: string;
  size?: number;
}

export function Ring({ current, goal, color, size = 110 }: Props) {
  const r = size * 0.42;
  const c = 2 * Math.PI * r;
  const p = Math.min(current / goal, 1);
  const offset = c - p * c;

  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--panel2)" strokeWidth={9} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={9}
          fill="none"
          strokeDasharray={c}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <b className="text-lg">{Math.round(current)}</b>
        <span className="text-[9.5px] text-sub">of {goal}</span>
      </div>
    </div>
  );
}

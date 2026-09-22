interface Props {
  color: string;
  size?: number;
}

export function Dot({ color, size = 9 }: Props) {
  return (
    <span
      className="inline-block flex-shrink-0 rounded-full"
      style={{ width: size, height: size, background: color }}
    />
  );
}

import { clsx } from "@/lib/clsx";

interface TickerItem {
  ticker: string;
  price: number;
  chg: number;
}

interface Props {
  items: TickerItem[];
}

export function TickerTape({ items }: Props) {
  // Doubled for a seamless loop: the track scrolls exactly -50%, so the
  // second copy lines up perfectly with the first as it resets.
  const doubled = [...items, ...items];

  return (
    <div className="mb-5 overflow-hidden border border-border">
      <div className="animate-ticker flex w-max gap-8 whitespace-nowrap py-2.5">
        {doubled.map((item, i) => (
          <span key={`${item.ticker}-${i}`} className="flex items-center gap-2 font-mono text-[11px]">
            <b className="text-text">{item.ticker}</b>
            <span className="text-sub">{item.price.toFixed(2)}</span>
            <span className={clsx(item.chg >= 0 ? "text-pos" : "text-neg")}>
              {item.chg >= 0 ? "▲" : "▼"} {Math.abs(item.chg).toFixed(2)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

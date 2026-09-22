import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useStocksStore } from "@/store/useStocksStore";
import { AreaChart } from "@/components/ui/AreaChart";
import { Sparkline } from "@/components/ui/Sparkline";
import { heldEquityValue } from "@/lib/stockInsights";
import { fmt, pctS } from "@/lib/format";
import { clsx } from "@/lib/clsx";

const SECTOR_PALETTE = ["var(--blue)", "var(--accent)", "var(--purple)", "var(--orange)", "var(--yellow)"];

export function PortfolioView() {
  const stocks = useStocksStore((s) => s.stocks);
  const navigate = useNavigate();

  const held = stocks.filter((s) => s.held);
  const totalVal = heldEquityValue(stocks);
  const totalCost = held.reduce((s, x) => s + (x.cost ?? 0) * (x.shares ?? 0), 0);
  const gain = totalVal - totalCost;

  const portfolioSeries = useMemo(() => {
    if (held.length === 0) return [];
    const length = held[0].history.length;
    return Array.from({ length }, (_, i) => held.reduce((s, x) => s + x.history[i].close * (x.shares ?? 0), 0));
  }, [held]);

  const sectorAlloc = useMemo(() => {
    const bySector = new Map<string, number>();
    for (const s of held) {
      const value = s.price * (s.shares ?? 0);
      bySector.set(s.sector, (bySector.get(s.sector) ?? 0) + value);
    }
    return [...bySector.entries()]
      .map(([name, value], i) => ({ name, pct: (value / totalVal) * 100, color: SECTOR_PALETTE[i % SECTOR_PALETTE.length] }))
      .sort((a, b) => b.pct - a.pct);
  }, [held, totalVal]);

  return (
    <div className="mx-auto max-w-[820px]">
      <div className="pt-2.5 text-center">
        <span className="font-mono text-[13px] tracking-[1px] text-sub">YOUR PORTFOLIO</span>
        <div className="my-1 font-mono text-[44px] font-extrabold leading-none tracking-tight">{fmt(totalVal)}</div>
        <div className={clsx("text-sm font-semibold", gain >= 0 ? "text-pos" : "text-neg")}>
          {gain >= 0 ? "▲" : "▼"} {fmt(Math.abs(gain))} ({pctS(Math.abs(gain) / totalCost)}) all-time
        </div>
      </div>

      {portfolioSeries.length > 0 && (
        <div className="mt-4">
          <AreaChart data={portfolioSeries} color={gain >= 0 ? "var(--pos)" : "var(--neg)"} width={780} height={200} />
        </div>
      )}

      <div className="my-9 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">Holdings — tap for full quote</div>
      {held.map((s) => {
        const g = (s.price - (s.cost ?? 0)) * (s.shares ?? 0);
        const gp = (s.price - (s.cost ?? 0)) / (s.cost ?? 1);
        return (
          <div
            key={s.ticker}
            onClick={() => navigate(`/stocks/portfolio/${s.ticker.toLowerCase()}`)}
            className="group flex cursor-pointer items-center justify-between gap-4 border-t border-border py-4 first:border-t-0 hover:bg-panel3"
          >
            <div className="flex items-center gap-3.5">
              <div>
                <div className="font-bold group-hover:underline">{s.ticker}</div>
                <div className="text-[11.5px] text-sub">
                  {s.shares} sh @ ${(s.cost ?? 0).toFixed(2)}
                </div>
              </div>
            </div>
            <div className="opacity-85">
              <Sparkline data={s.history.slice(-30).map((p) => p.close)} color={g >= 0 ? "var(--pos)" : "var(--neg)"} width={90} height={30} />
            </div>
            <div className="min-w-[110px] text-right">
              <div className="font-bold">${s.price.toFixed(2)}</div>
              <div className={clsx("text-[11.5px]", g >= 0 ? "text-pos" : "text-neg")}>
                {g >= 0 ? "+" : ""}
                {fmt(g)} ({pctS(gp)})
              </div>
            </div>
          </div>
        );
      })}

      <div className="my-9 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">Sector allocation</div>
      <div className="flex flex-wrap gap-0 border border-border">
        {sectorAlloc.map((s) => (
          <div key={s.name} className="border-b border-r border-border p-3.5" style={{ width: "50%" }}>
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-sub">{s.name}</span>
            <span className="flex items-center gap-1.5 text-sm font-bold">
              <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
              {s.pct.toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
      <div className="mt-2 text-[11px] text-sub">Computed live from current share values — not a fixed allocation target.</div>
    </div>
  );
}

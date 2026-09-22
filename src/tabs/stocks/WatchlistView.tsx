import { useNavigate } from "react-router-dom";
import { useStocksStore } from "@/store/useStocksStore";
import { Sparkline } from "@/components/ui/Sparkline";
import { clsx } from "@/lib/clsx";

export function WatchlistView() {
  const stocks = useStocksStore((s) => s.stocks);
  const navigate = useNavigate();
  const watch = stocks.filter((s) => !s.held);

  return (
    <div className="mx-auto max-w-[820px]">
      <div className="mb-1.5 mt-0 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">
        Watchlist — not currently held
      </div>
      {watch.map((s) => (
        <div
          key={s.ticker}
          onClick={() => navigate(`/stocks/watchlist/${s.ticker.toLowerCase()}`)}
          className="group flex cursor-pointer items-center justify-between gap-4 border-t border-border py-4 first:border-t-0 hover:bg-panel3"
        >
          <div>
            <div className="font-bold group-hover:underline">{s.ticker}</div>
            <div className="text-[11.5px] text-sub">{s.name}</div>
          </div>
          <div className="opacity-85">
            <Sparkline data={s.history.slice(-30).map((p) => p.close)} color={s.chg >= 0 ? "var(--pos)" : "var(--neg)"} width={90} height={30} />
          </div>
          <div className="min-w-[110px] text-right">
            <div className="font-bold">${s.price.toFixed(2)}</div>
            <div className={clsx("text-[11.5px]", s.chg >= 0 ? "text-pos" : "text-neg")}>
              {s.chg >= 0 ? "+" : ""}
              {s.chg.toFixed(2)}%
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

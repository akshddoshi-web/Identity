import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useStocksStore } from "@/store/useStocksStore";
import { insightForTicker } from "@/lib/stockInsights";
import { AreaChart } from "@/components/ui/AreaChart";
import { CandlestickChart } from "@/components/ui/CandlestickChart";
import { Badge } from "@/components/ui/Badge";
import { sliceRange } from "@/lib/ohlc";
import { fmt, pctS } from "@/lib/format";
import { CHART_RANGES, type ChartRange } from "@/types/stocks";
import { clsx } from "@/lib/clsx";

interface Props {
  ticker: string;
  backTo: string;
}

const TONE_BADGE_LABEL: Record<string, string> = { ok: "On track", warn: "Flagged", crit: "Risk flag" };

export function StockDetailView({ ticker, backTo }: Props) {
  const navigate = useNavigate();
  const stocks = useStocksStore((s) => s.stocks);
  const stock = stocks.find((s) => s.ticker.toLowerCase() === ticker.toLowerCase());
  const [range, setRange] = useState<ChartRange>("1Y");
  const [chartType, setChartType] = useState<"line" | "candles">("line");

  const insight = useMemo(() => (stock ? insightForTicker(stocks, stock.ticker) : undefined), [stocks, stock]);
  const sliced = useMemo(() => (stock ? sliceRange(stock.history, range) : []), [stock, range]);

  if (!stock) {
    return (
      <div className="mx-auto max-w-[820px] py-16 text-center text-sm text-sub">
        Couldn't find "{ticker.toUpperCase()}". <br />
        <button className="mt-3 text-xs text-sub underline" onClick={() => navigate(backTo)}>
          ← Back to list
        </button>
      </div>
    );
  }

  const g = stock.held ? (stock.price - (stock.cost ?? 0)) * (stock.shares ?? 0) : null;
  const gp = stock.held ? (stock.price - (stock.cost ?? 0)) / (stock.cost ?? 1) : null;
  const lineColor = stock.chg >= 0 ? "var(--pos)" : "var(--neg)";

  return (
    <div className="mx-auto max-w-[820px]">
      <span className="mb-2.5 inline-block cursor-pointer text-xs text-sub hover:text-text" onClick={() => navigate(backTo)}>
        ← Back to list
      </span>

      <div className="pt-1 text-center">
        <span className="font-mono text-[13px] tracking-[1px] text-sub">
          {stock.ticker} · {stock.name.toUpperCase()}
        </span>
        <div className="my-1 font-mono text-[44px] font-extrabold leading-none tracking-tight">${stock.price.toFixed(2)}</div>
        <div className={clsx("flex items-center justify-center gap-2 text-sm font-semibold", stock.chg >= 0 ? "text-pos" : "text-neg")}>
          {stock.chg >= 0 ? "▲" : "▼"} {Math.abs(stock.chg).toFixed(2)}% today
          {insight && <Badge tone={insight.tone}>{TONE_BADGE_LABEL[insight.tone]}</Badge>}
        </div>
      </div>

      <div className="mt-4">
        {chartType === "line" ? (
          <AreaChart data={sliced.map((p) => p.close)} color={lineColor} width={780} height={220} />
        ) : (
          <CandlestickChart data={sliced} width={780} height={220} />
        )}
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-center gap-4">
        <div className="flex w-fit gap-0">
          {CHART_RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={clsx(
                "border-b-2 px-4 py-2 font-mono text-xs font-semibold",
                range === r ? "border-text text-text" : "border-transparent text-sub hover:text-text",
              )}
            >
              {r}
            </button>
          ))}
        </div>
        <div className="flex border border-border">
          {(["line", "candles"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setChartType(t)}
              className={clsx(
                "px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wide",
                chartType === t ? "bg-text text-bg" : "text-sub hover:bg-panel3 hover:text-text",
              )}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {stock.held && g !== null && gp !== null && (
        <div className="mt-5 text-center text-[13px] text-sub">
          Holding <b className="text-text">{stock.shares} shares</b> @ avg ${(stock.cost ?? 0).toFixed(2)} —{" "}
          <span className={g >= 0 ? "text-pos" : "text-neg"}>
            {g >= 0 ? "+" : ""}
            {fmt(g)}
          </span>{" "}
          unrealized ({gp >= 0 ? "+" : ""}
          {pctS(gp)})
        </div>
      )}

      <div className="my-9 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">Key statistics</div>
      <div className="flex flex-wrap border-t border-border">
        {[
          ["Market Cap", stock.mktCap],
          ["P/E Ratio", stock.pe],
          ["Volume", stock.vol],
          ["Avg Volume", stock.avgVol],
          ["Day Range", stock.dayRange],
          ["52-Wk Range", stock.wk52],
          ["Sector", stock.sector],
          ["Status", stock.held ? "Held" : "Watchlist"],
        ].map(([label, value]) => (
          <div key={label} className="w-1/2 border-b border-border py-3 sm:w-1/4">
            <span className="mb-0.5 block font-mono text-[10px] uppercase tracking-wide text-sub">{label}</span>
            <span className="text-sm font-bold">{value}</span>
          </div>
        ))}
      </div>

      {insight && (
        <div className="mt-5 border-t border-border pt-3.5 text-[13px] text-sub">{insight.note}</div>
      )}

      <div className="my-9 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">News</div>
      {stock.news.map((n) => (
        <div key={n.headline} className="border-t border-border py-3.5 text-[12.5px] first:border-t-0">
          {n.headline}
          <div className="mt-1 font-mono text-[11px] text-sub">
            {n.source} · {n.age} ago
          </div>
        </div>
      ))}
    </div>
  );
}

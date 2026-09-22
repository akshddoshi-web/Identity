import { useMemo } from "react";
import { useStocksStore } from "@/store/useStocksStore";
import { buildStockInsights } from "@/lib/stockInsights";
import { Card } from "@/components/ui/Card";
import { clsx } from "@/lib/clsx";

const ICON: Record<string, string> = { crit: "🔴", warn: "🟡", ok: "🟢" };

export function StockInsightsView() {
  const stocks = useStocksStore((s) => s.stocks);
  const insights = useMemo(() => buildStockInsights(stocks), [stocks]);

  return (
    <div className="grid grid-cols-12 gap-3.5">
      <Card span={12} title="Portfolio opinions" hint="Rule-based — every flag names the threshold it crossed">
        {insights.map((i) => (
          <div
            key={i.ticker}
            className={clsx(
              "mb-2.5 flex gap-3 border border-border bg-panel3 p-3.5 last:mb-0",
              i.tone === "crit" && "border-l-[3px] border-l-neg",
              i.tone === "warn" && "border-l-[3px] border-l-warn",
            )}
          >
            <div className="mt-px text-lg leading-none">{ICON[i.tone]}</div>
            <div>
              <b className="mb-0.5 block text-[13px]">{i.title}</b>
              <span className="text-xs leading-relaxed text-sub">{i.note}</span>
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}

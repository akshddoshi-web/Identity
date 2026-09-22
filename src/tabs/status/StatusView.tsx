import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useHomeStore } from "@/store/useHomeStore";
import { useStocksStore } from "@/store/useStocksStore";
import { useFitnessStore } from "@/store/useFitnessStore";
import { usePlannerStore } from "@/store/usePlannerStore";
import { buildStatusItems, type StatusDomain } from "@/lib/statusOverview";
import { Card } from "@/components/ui/Card";
import { clsx } from "@/lib/clsx";

const DOMAIN_HREF: Record<StatusDomain, string> = {
  Home: "/home/insights",
  Stocks: "/stocks/portfolio",
  Fitness: "/fitness/today",
  Planner: "/planner/week",
};

export function StatusView() {
  const avenues = useHomeStore((s) => s.avenues);
  const stocks = useStocksStore((s) => s.stocks);
  const fitness = useFitnessStore((s) => s);
  const week = usePlannerStore((s) => s.week);
  const navigate = useNavigate();

  const items = useMemo(
    () => buildStatusItems({ avenues, stocks, fitness, week }),
    [avenues, stocks, fitness, week],
  );

  const critCount = items.filter((i) => i.tone === "crit").length;
  const warnCount = items.filter((i) => i.tone === "warn").length;

  return (
    <div className="grid grid-cols-12 gap-3.5">
      <Card
        span={12}
        title="Status"
        hint="Every domain's accountability check, ranked worst-first — one function, five domains, four of them with something to say right now"
      >
        {items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-14 text-center">
            <div className="text-3xl">✅</div>
            <div className="text-[15px] font-bold">You're on track everywhere</div>
            <div className="max-w-xs text-xs text-sub">
              Every tracked target across Home, Stocks, Fitness, and Planner is inside its range right
              now. Nothing needs your attention.
            </div>
          </div>
        ) : (
          <>
            <div className="mb-4 flex gap-4 font-mono text-[11px] uppercase tracking-wide text-sub">
              <span>
                <b className="text-neg">{critCount}</b> critical
              </span>
              <span>
                <b className="text-warn">{warnCount}</b> warning
              </span>
            </div>
            {items.map((item) => (
              <div
                key={item.id}
                onClick={() => navigate(item.href)}
                className={clsx(
                  "mb-2.5 flex cursor-pointer gap-3 border border-border bg-panel3 p-3.5 last:mb-0 hover:border-text",
                  item.tone === "crit" ? "border-l-[3px] border-l-neg" : "border-l-[3px] border-l-warn",
                )}
              >
                <div className="mt-px text-lg leading-none">{item.tone === "crit" ? "🔴" : "🟡"}</div>
                <div className="flex-1">
                  <div className="mb-0.5 flex items-center gap-2">
                    <span className="border border-border bg-panel px-1.5 py-0.5 font-mono text-[9.5px] font-bold uppercase tracking-wide text-sub">
                      {item.domain}
                    </span>
                    <b className="text-[13px]">{item.title}</b>
                  </div>
                  <span className="text-xs leading-relaxed text-sub">{item.body}</span>
                </div>
                <div className="flex-shrink-0 self-center font-mono text-[10px] text-sub">→</div>
              </div>
            ))}
          </>
        )}
      </Card>

      <div className="col-span-12 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        {(Object.keys(DOMAIN_HREF) as StatusDomain[]).map((domain) => (
          <button
            key={domain}
            onClick={() => navigate(DOMAIN_HREF[domain])}
            className="border border-border px-3 py-2.5 text-left font-mono text-[11px] uppercase tracking-wide text-sub hover:border-text hover:text-text"
          >
            {domain} →
          </button>
        ))}
      </div>
    </div>
  );
}

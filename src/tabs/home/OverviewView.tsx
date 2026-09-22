import { useMemo } from "react";
import { useHomeStore } from "@/store/useHomeStore";
import { buildAvenueAlerts } from "@/lib/accountability";
import { Card } from "@/components/ui/Card";
import { BarChart } from "@/components/ui/BarChart";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Dot } from "@/components/ui/Dot";
import { fmt } from "@/lib/format";
import { clsx } from "@/lib/clsx";

export function OverviewView() {
  const accounts = useHomeStore((s) => s.accounts);
  const avenues = useHomeStore((s) => s.avenues);
  const monthlyTrend = useHomeStore((s) => s.monthlyTrend);

  const totalBudget = avenues.reduce((s, a) => s + a.budget, 0);
  const totalSpent = avenues.reduce((s, a) => s + a.spent, 0);
  const netWorth = accounts.reduce((s, a) => s + a.balance, 0);
  const alerts = useMemo(() => buildAvenueAlerts(avenues), [avenues]);

  return (
    <div className="grid grid-cols-12 gap-3.5">
      <Card span={3} title="Net worth" hint="All linked accounts">
        <div className="flex items-baseline justify-between">
          <span className="text-2xl font-extrabold">{fmt(netWorth)}</span>
        </div>
      </Card>

      <Card span={3} title="This month" hint="Spend vs budget">
        <div className="flex items-baseline justify-between">
          <span className="text-2xl font-extrabold">{fmt(totalSpent)}</span>
          <span className="text-xs text-sub">of {fmt(totalBudget)}</span>
        </div>
        <ProgressBar
          pct={(totalSpent / totalBudget) * 100}
          color={totalSpent > totalBudget ? "var(--red)" : "var(--accent)"}
        />
      </Card>

      <Card span={3} title="Income (cycle)" hint="Advantest paycheck">
        <div className="flex items-baseline justify-between">
          <span className="text-2xl font-extrabold">$2,150</span>
          <span className="text-xs text-pos">on track</span>
        </div>
      </Card>

      <Card span={3} title="Accountability" hint="Active flags">
        <div className="flex items-baseline justify-between">
          <span
            className="text-2xl font-extrabold"
            style={{ color: alerts.some((a) => a.tone === "crit") ? "var(--red)" : "var(--orange)" }}
          >
            {alerts.length}
          </span>
        </div>
      </Card>

      <Card span={8} title="Spending trend" hint="Last 6 months, total spend">
        <BarChart data={monthlyTrend.map((m) => ({ label: m.month, value: m.value }))} color="var(--blue)" />
      </Card>

      <Card span={4} title="Alerts" hint="Rule-based, checked daily">
        {alerts.length ? (
          alerts.slice(0, 2).map((a) => (
            <div
              key={a.id}
              className={clsx(
                "mb-2.5 flex gap-3 border border-border bg-panel3 p-3.5",
                a.tone === "crit" ? "border-l-[3px] border-l-neg" : "border-l-[3px] border-l-warn",
              )}
            >
              <div className="mt-px text-lg leading-none">{a.tone === "crit" ? "🔴" : "🟡"}</div>
              <div>
                <b className="mb-0.5 block text-[13px]">{a.title}</b>
                <span className="text-xs leading-relaxed text-sub">{a.body}</span>
              </div>
            </div>
          ))
        ) : (
          <div className="py-3.5 text-xs text-sub">Nothing flagged.</div>
        )}
      </Card>

      <Card span={12} title="Spending by avenue" hint="Every avenue's spend vs its monthly budget">
        {avenues.map((a) => {
          const p = Math.min(a.spent / a.budget, 1) * 100;
          const over = a.spent > a.budget;
          return (
            <div key={a.id} className="flex items-center justify-between gap-3 border-t border-border py-3 first:border-t-0">
              <div className="flex min-w-[150px] items-center gap-2.5 text-[13.5px] font-semibold">
                <Dot color={a.color} />
                {a.name}
              </div>
              <div className="flex-1">
                <div className="mb-1 flex justify-between text-xs text-sub">
                  <span>{fmt(a.spent)}</span>
                  <span>{fmt(a.budget)} budget</span>
                </div>
                <ProgressBar pct={p} color={over ? "var(--red)" : a.color} size="sm" />
              </div>
              <div className={clsx("min-w-[74px] text-right text-[13px] font-bold", over && "text-neg")}>
                {over ? "+" : ""}
                {fmt(a.spent - a.budget)}
              </div>
            </div>
          );
        })}
      </Card>
    </div>
  );
}

import { useHomeStore } from "@/store/useHomeStore";
import { Sparkline } from "@/components/ui/Sparkline";
import { Dot } from "@/components/ui/Dot";
import { Avatar } from "@/components/ui/Avatar";
import { Pill } from "@/components/ui/Pill";
import { fmt, pctS } from "@/lib/format";
import { chargeCountdown } from "@/lib/dates";
import { clsx } from "@/lib/clsx";

export function InsightsView() {
  const accounts = useHomeStore((s) => s.accounts);
  const netWorthHistory = useHomeStore((s) => s.netWorthHistory);
  const insights = useHomeStore((s) => s.insights);
  const subscriptions = useHomeStore((s) => s.subscriptions);
  const cancelSubscription = useHomeStore((s) => s.cancelSubscription);

  const netWorth = accounts.reduce((s, a) => s + a.balance, 0);
  const start = netWorthHistory[0];
  const chg = netWorth - start;
  const chgPct = chg / start;
  const subCost = subscriptions.reduce((s, x) => s + x.cost, 0);

  return (
    <div className="mx-auto max-w-rm">
      <div className="mb-3.5 flex flex-wrap items-end justify-between gap-2.5 pb-5">
        <div>
          <div className="font-mono text-[46px] font-extrabold leading-none tracking-tight">{fmt(netWorth)}</div>
          <div className={clsx("mt-1 text-xs", chg >= 0 ? "text-pos" : "text-neg")}>
            {chg >= 0 ? "+" : ""}
            {fmt(chg)} ({chgPct >= 0 ? "+" : ""}
            {pctS(chgPct)}) past 12 mo
          </div>
        </div>
        <div className="flex-shrink-0">
          <Sparkline data={netWorthHistory} color={chg >= 0 ? "var(--pos)" : "var(--neg)"} width={200} height={56} />
        </div>
      </div>

      <div className="my-8 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">What we're watching</div>
      {insights.map((i) => (
        <div key={i.id} className="flex gap-3.5 border-t border-border py-4.5 first:border-t-0">
          <Dot
            color={i.tone === "money" ? "var(--pos)" : i.tone === "warn" ? "var(--warn)" : i.tone === "crit" ? "var(--neg)" : "var(--text)"}
            size={8}
          />
          <div>
            <b className="mb-0.5 block text-sm">{i.title}</b>
            <p className="m-0 text-[12.5px] leading-relaxed text-sub">{i.body}</p>
            {i.cta && (
              <div className="mt-2">
                <Pill>{i.cta}</Pill>
              </div>
            )}
          </div>
        </div>
      ))}

      <div className="my-8 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">
        Subscriptions · {fmt(subCost)}/mo across {subscriptions.length}
      </div>
      {subscriptions.map((s) => {
        const countdown = chargeCountdown(s.nextChargeDate);
        return (
          <div key={s.id} className="flex items-center gap-3 border-t border-border py-3 first:border-t-0">
            <Avatar label={s.name} size={36} />
            <div className="flex-1">
              <b className="block text-sm">{s.name}</b>
              <span className={clsx("text-[11px]", s.unused ? "text-warn" : "text-sub")}>
                {s.unused ? "Unused · " : ""}Last used {s.lastUsed}
              </span>
              <div
                className={clsx(
                  "mt-0.5 font-mono text-[10px] uppercase tracking-wide",
                  countdown.overdue ? "text-neg" : countdown.urgent ? "text-warn" : "text-sub",
                )}
              >
                {countdown.label}
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm font-bold">{fmt(s.cost)}</div>
              {s.unused && (
                <Pill className="mt-1 px-2.5 py-[3px] text-[10px]" onClick={() => cancelSubscription(s.id)}>
                  Cancel
                </Pill>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

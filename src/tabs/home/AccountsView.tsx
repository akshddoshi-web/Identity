import { useHomeStore } from "@/store/useHomeStore";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { fmt } from "@/lib/format";
import { clsx } from "@/lib/clsx";

const TYPE_ACCENT: Record<string, string> = {
  Checking: "var(--blue)",
  "Credit Card": "var(--red)",
  Savings: "var(--pos)",
  Investing: "var(--purple)",
};

export function AccountsView() {
  const accounts = useHomeStore((s) => s.accounts);
  const netWorth = accounts.reduce((s, a) => s + a.balance, 0);

  return (
    <div className="grid grid-cols-12 gap-3.5">
      <Card span={12} title="Linked accounts">
        <div className="mb-5 text-xs text-sub">
          Net worth: <b className="text-text">{fmt(netWorth)}</b>
        </div>

        <div className="scrollbar-thin -mx-1 flex snap-x snap-mandatory gap-0 overflow-x-auto px-1 pb-4">
          {accounts.map((a, idx) => {
            const accent = TYPE_ACCENT[a.type] ?? "var(--text)";
            return (
              <div
                key={a.id}
                className={clsx(
                  "group relative flex h-44 w-72 flex-shrink-0 snap-start flex-col justify-between border border-border bg-panel3 p-5 transition-all duration-200 hover:z-10 hover:-translate-y-1.5",
                  idx > 0 && "-ml-14 hover:ml-0",
                )}
                style={{ background: "linear-gradient(155deg, var(--panel3), var(--panel))" }}
              >
                <div className="flex items-start justify-between">
                  <div className="font-mono text-[10px] uppercase tracking-[1.5px] text-sub">{a.type}</div>
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: accent }} />
                </div>
                <div>
                  <div className="mb-1 text-sm font-semibold">{a.name}</div>
                  <div className="font-mono text-[11px] tracking-[3px] text-sub">•••• {a.last4}</div>
                </div>
                <div className={clsx("font-mono text-xl font-bold", a.balance < 0 && "text-neg")}>
                  {fmt(a.balance)}
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-3.5">
          <Pill>+ Link another account</Pill>
        </div>
      </Card>
    </div>
  );
}

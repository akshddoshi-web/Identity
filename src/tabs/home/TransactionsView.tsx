import { useMemo, useState } from "react";
import { useHomeStore } from "@/store/useHomeStore";
import { Card } from "@/components/ui/Card";
import { Avatar } from "@/components/ui/Avatar";
import { fmt } from "@/lib/format";
import { clsx } from "@/lib/clsx";

export function TransactionsView() {
  const transactions = useHomeStore((s) => s.transactions);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("All");

  const cats = useMemo(() => ["All", ...new Set(transactions.map((t) => t.cat))], [transactions]);
  const filtered = transactions.filter(
    (t) => (filter === "All" || t.cat === filter) && t.merchant.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="grid grid-cols-12 gap-3.5">
      <Card span={12} title="All transactions" hint="Search and filter by category">
        <input
          className="mb-3 w-full border border-border bg-panel2 px-3 py-2.5 text-[13px] text-text placeholder:text-sub focus:outline-none"
          placeholder="Search merchant..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="mb-3.5 flex flex-wrap gap-1.5">
          {cats.map((c) => (
            <button
              key={c}
              onClick={() => setFilter(c)}
              className={clsx(
                "rounded-full border border-border px-2.5 py-1 text-[11.5px] font-semibold",
                filter === c ? "border-text bg-text text-bg" : "bg-panel2 text-sub",
              )}
            >
              {c}
            </button>
          ))}
        </div>

        {filtered.length === 0 ? (
          <div className="py-3.5 text-xs text-sub">No transactions match.</div>
        ) : (
          <div>
            {filtered.map((t) => (
              <div key={t.id} className="flex items-center gap-3 border-t border-border py-2.5 first:border-t-0">
                <Avatar label={t.merchant} size={32} />
                <div className="flex-1">
                  <div className="text-[13px] font-medium">{t.merchant}</div>
                  <div className="text-[11px] text-sub">{t.cat}</div>
                </div>
                <div className="text-[11px] text-sub">{t.date}</div>
                <div className={clsx("w-24 text-right text-[13px] font-semibold", t.amt >= 0 && "text-pos")}>
                  {fmt(t.amt)}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

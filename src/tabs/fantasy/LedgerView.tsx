import { useMemo } from "react";
import { useFantasyStore } from "@/store/useFantasyStore";
import { buildCombinedBalances, buildLeagueBalances } from "@/lib/fantasyLedger";
import { settleUp } from "@/lib/settleUp";
import { clsx } from "@/lib/clsx";

export function LedgerView() {
  const leagues = useFantasyStore((s) => s.leagues);

  const payments = useMemo(() => settleUp(buildCombinedBalances(leagues)), [leagues]);
  const youNet = useMemo(() => {
    const mine = buildCombinedBalances(leagues).filter((b) => b.who === "You");
    return mine.reduce((s, b) => s + b.amount, 0);
  }, [leagues]);

  return (
    <div className="mx-auto max-w-[640px]">
      <div className="mb-1.5 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">
        Settle up — all leagues
      </div>
      <div className="mb-2 text-xs text-sub">
        Minimum set of payments to settle every league's final-standings payout, computed across all{" "}
        {leagues.length} leagues at once — not one settle-up per league.
      </div>

      {payments.length === 0 ? (
        <div className="border border-border p-4 text-xs text-sub">Everyone's settled up — no payments owed.</div>
      ) : (
        payments.map((p, i) => (
          <div key={i} className="flex items-center justify-between border-t border-border py-3.5 first:border-t-0">
            <span>
              <b>{p.from}</b> <span className="text-sub">pays</span> <b>{p.to}</b>
            </span>
            <span className="font-mono font-bold">${p.amount.toFixed(2)}</span>
          </div>
        ))
      )}

      <div className="mt-3.5 border border-dashed border-border p-3 text-xs text-sub">
        Your net across all leagues:{" "}
        <b className={clsx(youNet >= 0 ? "text-pos" : "text-neg")}>
          {youNet >= 0 ? "+" : ""}${youNet.toFixed(2)}
        </b>
        . Friends pay each other back directly — nothing routes through Identity.
      </div>

      {leagues.map((l) => {
        const total = l.ledgerHistory.reduce((s, h) => s + h.you, 0);
        const leagueNet = buildLeagueBalances(l).find((b) => b.who === "You")?.amount ?? 0;
        return (
          <div key={l.id} className="mt-9">
            <div className="mb-1.5 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">
              Season points ledger — {l.name}
            </div>
            {l.ledgerHistory.map((h) => (
              <div key={h.week} className="flex justify-between border-t border-border py-3.5 first:border-t-0">
                <span>
                  {h.week} — {h.note}
                </span>
                <span className={clsx(h.you >= 0 ? "text-pos" : "text-neg")}>
                  {h.you >= 0 ? "+" : ""}${h.you}
                </span>
              </div>
            ))}
            <div className="mt-2 border border-dashed border-border p-3 text-xs text-sub">
              Weekly points running total: <b className="text-text">{total >= 0 ? "+" : ""}${total}</b>. Settle-up
              payout position for this league: <b className={clsx(leagueNet >= 0 ? "text-pos" : "text-neg")}>{leagueNet >= 0 ? "+" : ""}${leagueNet.toFixed(2)}</b>.
            </div>
          </div>
        );
      })}
    </div>
  );
}

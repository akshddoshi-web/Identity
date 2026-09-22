import { useFantasyStore } from "@/store/useFantasyStore";
import { Avatar } from "@/components/ui/Avatar";
import { clsx } from "@/lib/clsx";

const SALARY_CAP = 52000;

export function MyTeamView() {
  const leagues = useFantasyStore((s) => s.leagues);
  const activeLeagueId = useFantasyStore((s) => s.activeLeagueId);
  const league = leagues.find((l) => l.id === activeLeagueId) ?? leagues[0];

  if (league.myRoster.length === 0) {
    return (
      <div className="border border-border p-8 text-center text-xs text-sub">
        No roster data for this league in the demo — switch to Sunday Guys in the Lobby.
      </div>
    );
  }

  const total = league.myRoster.reduce((s, r) => s + r.pts, 0);
  const projTotal = league.myRoster.reduce((s, r) => s + r.proj, 0);
  const cap = league.myRoster.reduce((s, r) => s + r.salary, 0);
  const capPct = Math.min((cap / SALARY_CAP) * 100, 100);

  return (
    <div className="mx-auto max-w-[640px]">
      <div className="pb-1.5">
        <div className="font-mono text-[11px] uppercase tracking-[1.5px] text-sub">Your roster · Week 3</div>
        <div className="mt-1 flex flex-wrap items-baseline gap-3.5">
          <span className="font-mono text-[40px] font-extrabold leading-none">{total.toFixed(1)}</span>
          <span className="text-xs text-sub">projected {projTotal.toFixed(1)} pts</span>
        </div>
      </div>

      <div className="my-4">
        <div className="mb-1.5 flex justify-between font-mono text-[11px] text-sub">
          <span>SALARY CAP</span>
          <span>
            ${cap.toLocaleString()} / ${SALARY_CAP.toLocaleString()}
          </span>
        </div>
        <div className="h-4 overflow-hidden border border-border bg-panel">
          <div
            className="h-full"
            style={{
              width: `${capPct}%`,
              background: "repeating-linear-gradient(135deg, var(--text) 0 6px, var(--panel3) 6px 12px)",
            }}
          />
        </div>
      </div>

      {league.myRoster.map((r) => {
        const diff = r.pts - r.proj;
        return (
          <div key={r.name} className="mb-1.5 flex items-center justify-between border border-border bg-panel3 p-3 last:mb-0">
            <div className="flex items-center gap-3">
              <Avatar label={r.name} size={32} />
              <div>
                <span className="mr-2 border border-border bg-panel px-1.5 py-0.5 font-mono text-[10px] font-bold text-sub">
                  {r.pos}
                </span>
                <b className="text-[13px]">{r.name}</b>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="font-mono text-[11px] text-sub">${r.salary.toLocaleString()}</span>
              <span className="text-[11px] text-sub">proj {r.proj}</span>
              <span className="min-w-[50px] text-right font-bold">{r.pts.toFixed(1)}</span>
              <span className={clsx("min-w-[40px] text-right text-[11px]", diff >= 0 ? "text-pos" : "text-neg")}>
                {diff >= 0 ? "+" : ""}
                {diff.toFixed(1)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

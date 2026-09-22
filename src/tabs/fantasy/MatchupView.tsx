import { useFantasyStore } from "@/store/useFantasyStore";
import { Avatar } from "@/components/ui/Avatar";

export function MatchupView() {
  const leagues = useFantasyStore((s) => s.leagues);
  const activeLeagueId = useFantasyStore((s) => s.activeLeagueId);
  const league = leagues.find((l) => l.id === activeLeagueId) ?? leagues[0];
  const m = league.matchup;

  const totalProj = m.myProj + m.oppProj;
  const winProb = Math.round((m.myProj / totalProj) * 100);

  return (
    <div className="mx-auto max-w-[560px]">
      <div className="border-b border-border pb-6 pt-2 text-center">
        <div className="mb-4 font-mono text-[11px] uppercase tracking-[2px] text-sub">
          Week 3 · {league.name.toUpperCase()}{" "}
          {m.live ? <span className="text-pos">● LIVE</span> : <span>FINAL</span>}
        </div>
        <div className="flex items-center justify-center gap-6">
          <div className="flex flex-col items-center gap-2">
            <Avatar label="YOU" text="YOU" size={56} />
            <div className="font-mono text-[38px] font-extrabold leading-none">{m.myScore}</div>
            <div className="text-[11px] uppercase tracking-wide text-sub">proj {m.myProj}</div>
          </div>
          <div className="font-mono text-xs text-sub">VS</div>
          <div className="flex flex-col items-center gap-2">
            <Avatar label={m.opp} size={56} />
            <div className="font-mono text-[38px] font-extrabold leading-none">{m.oppScore}</div>
            <div className="text-[11px] uppercase tracking-wide text-sub">proj {m.oppProj}</div>
          </div>
        </div>
      </div>

      <div className="my-5">
        <div className="mb-1.5 flex justify-between font-mono text-[11px] text-sub">
          <span>WIN PROBABILITY</span>
          <span>{winProb}% — YOU</span>
        </div>
        <div className="flex h-[22px] overflow-hidden border border-border bg-panel">
          <div className="h-full bg-text" style={{ width: `${winProb}%` }} />
        </div>
      </div>

      <div className="mb-1.5 mt-9 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">League activity</div>
      {league.feed.map((f, i) => (
        <div key={i} className="flex justify-between gap-4 border-t border-border py-3.5 first:border-t-0">
          <span className="flex-shrink-0 font-mono text-[11px] text-sub">{f.time}</span>
          <span>{f.text}</span>
        </div>
      ))}
    </div>
  );
}

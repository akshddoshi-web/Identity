import { useNavigate } from "react-router-dom";
import { useFantasyStore } from "@/store/useFantasyStore";
import { clsx } from "@/lib/clsx";

export function LobbyView() {
  const leagues = useFantasyStore((s) => s.leagues);
  const activeLeagueId = useFantasyStore((s) => s.activeLeagueId);
  const setActiveLeague = useFantasyStore((s) => s.setActiveLeague);
  const navigate = useNavigate();

  const activeLeague = leagues.find((l) => l.id === activeLeagueId) ?? leagues[0];

  return (
    <div>
      <div className="scrollbar-thin mb-5 overflow-x-auto whitespace-nowrap border border-border px-3.5 py-2.5 font-mono text-[11px] text-sub">
        WK 3 LIVE &nbsp;·&nbsp;{" "}
        {leagues
          .map((l) => `${l.name}: YOU ${l.matchup.myScore} — ${l.matchup.oppScore} ${l.matchup.opp}`)
          .join("   ///   ")}
      </div>

      <div className="mb-1.5 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">Your leagues — tap to switch</div>
      <div className="scrollbar-thin mb-9 flex gap-3 overflow-x-auto pb-3">
        {leagues.map((l) => {
          const me = l.standings.find((s) => s.name === "You")!;
          const active = l.id === activeLeagueId;
          return (
            <div
              key={l.id}
              onClick={() => setActiveLeague(l.id)}
              className={clsx(
                "min-w-[200px] flex-shrink-0 cursor-pointer border border-border p-3.5",
                active ? "bg-text text-bg" : "bg-panel3 hover:border-text",
              )}
            >
              <div className="mb-2.5 text-[13px] font-bold">{l.name}</div>
              <div className="font-mono text-2xl font-extrabold">{me.pts.toFixed(1)}</div>
              <div className={clsx("mt-1.5 text-[10.5px]", active ? "text-bg/60" : "text-sub")}>
                #{me.rank} of {l.standings.length} · ${l.potTotal} pot
              </div>
            </div>
          );
        })}
      </div>

      <div className="mb-1.5 flex items-center justify-between">
        <div className="font-mono text-[11px] uppercase tracking-[1.5px] text-sub">{activeLeague.name} — full standings</div>
        {activeLeague.draftBoard && (
          <button
            onClick={() => navigate("/fantasy/lobby/draft")}
            className="font-mono text-[11px] text-sub underline hover:text-text"
          >
            View draft board →
          </button>
        )}
      </div>
      {activeLeague.standings.map((s) => (
        <div key={s.name} className="flex items-center justify-between border-t border-border py-3.5 first:border-t-0">
          <span>
            <span className="mr-1 inline-block w-5 text-sub">#{s.rank}</span>
            {s.name} <span className="text-sub">({s.w}-{s.l})</span>
          </span>
          <span>{s.pts.toFixed(1)} pts</span>
        </div>
      ))}

      <div className="mt-3.5 border border-dashed border-border p-3 text-xs text-sub">
        Final standings generate a suggested settle-up split — friends pay each other back directly, nothing routes
        through Identity.
      </div>
    </div>
  );
}

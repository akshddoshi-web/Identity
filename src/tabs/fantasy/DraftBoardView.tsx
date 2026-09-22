import { useNavigate } from "react-router-dom";
import { useFantasyStore } from "@/store/useFantasyStore";

export function DraftBoardView() {
  const navigate = useNavigate();
  const leagues = useFantasyStore((s) => s.leagues);
  const activeLeagueId = useFantasyStore((s) => s.activeLeagueId);
  const league = leagues.find((l) => l.id === activeLeagueId) ?? leagues[0];
  const board = league.draftBoard;

  if (!board) {
    return (
      <div>
        <span
          className="mb-2.5 inline-block cursor-pointer text-xs text-sub hover:text-text"
          onClick={() => navigate("/fantasy/lobby")}
        >
          ← Back to lobby
        </span>
        <div className="border border-border p-8 text-center text-xs text-sub">
          No draft record for this league in the demo — switch to Sunday Guys in the Lobby.
        </div>
      </div>
    );
  }

  const picksByRound = Array.from({ length: board.rounds }, (_, i) =>
    board.picks.filter((p) => p.round === i + 1).sort((a, b) => a.pickInRound - b.pickInRound),
  );

  return (
    <div>
      <span
        className="mb-2.5 inline-block cursor-pointer text-xs text-sub hover:text-text"
        onClick={() => navigate("/fantasy/lobby")}
      >
        ← Back to lobby
      </span>

      <div className="mb-1 font-mono text-[11px] uppercase tracking-[2px] text-sub">{league.name}</div>
      <div className="mb-6 text-lg font-bold">Draft board — snake order, {board.rounds} rounds</div>

      <div className="border border-border">
        <div className="grid border-b border-border" style={{ gridTemplateColumns: `repeat(${board.teams.length}, 1fr)` }}>
          {board.teams.map((team) => (
            <div
              key={team}
              className="border-r border-border p-2.5 text-center font-mono text-[11px] font-bold uppercase tracking-wide last:border-r-0"
            >
              {team}
            </div>
          ))}
        </div>

        {picksByRound.map((picks, roundIdx) => {
          return (
            <div
              key={roundIdx}
              className="grid border-b border-border last:border-b-0"
              style={{ gridTemplateColumns: `repeat(${board.teams.length}, 1fr)` }}
            >
              {board.teams.map((team) => {
                const pick = picks.find((p) => p.team === team)!;
                return (
                  <div key={team} className="border-r border-border p-2.5 last:border-r-0">
                    <div className="font-mono text-[9.5px] text-sub">
                      R{pick.round}.{pick.pickInRound} · #{pick.overallPick}
                    </div>
                    <div className="mt-1 flex items-center gap-1.5">
                      <span className="border border-border bg-panel3 px-1 py-0.5 font-mono text-[9px] font-bold text-sub">
                        {pick.pos}
                      </span>
                      <span className="text-[12px] font-semibold">{pick.player}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      <div className="mt-3.5 text-[11px] text-sub">
        Snake order — the pick order reverses every round (round 1: {board.teams.join(" → ")}, round 2 reversed),
        so no team drafts twice in a row.
      </div>
    </div>
  );
}

import type { DraftPick, FantasyData, League } from "@/types/fantasy";

// Every league/standing/roster/matchup/feed/ledger field mirrors the
// prototype's `leagues` array exactly. `draftBoard` is new — the prototype
// has no draft data, so it's authored fresh below (Sunday Guys only; Office
// Pool intentionally has none, the same "no data yet" pattern the prototype
// itself uses for Office Pool's empty myRoster).
const sundayGuys: League = {
  id: "sunday-guys",
  name: "Sunday Guys",
  season: "2026 · Week 3 of 17",
  buyIn: 10,
  potTotal: 40,
  standings: [
    { name: "You", pts: 142.6, rank: 1, w: 2, l: 1 },
    { name: "Mike", pts: 128.4, rank: 2, w: 2, l: 1 },
    { name: "Sarah", pts: 119.0, rank: 3, w: 1, l: 2 },
    { name: "Priya", pts: 104.2, rank: 4, w: 1, l: 2 },
  ],
  myRoster: [
    { pos: "QB", name: "J. Allen", pts: 24.3, proj: 22.8, salary: 8400 },
    { pos: "RB", name: "B. Robinson", pts: 18.1, proj: 16.5, salary: 7100 },
    { pos: "RB", name: "D. Henry", pts: 15.6, proj: 17.2, salary: 7800 },
    { pos: "WR", name: "A. St. Brown", pts: 19.4, proj: 15.9, salary: 7500 },
    { pos: "WR", name: "D. Adams", pts: 11.2, proj: 13.1, salary: 6600 },
    { pos: "TE", name: "T. Kelce", pts: 9.8, proj: 11.4, salary: 5200 },
    { pos: "FLEX", name: "C. Lamb", pts: 14.0, proj: 15.0, salary: 7300 },
    { pos: "DEF", name: "Ravens", pts: 8.0, proj: 7.5, salary: 2900 },
  ],
  matchup: { opp: "Mike", myScore: 142.6, oppScore: 128.4, myProj: 138.2, oppProj: 131.0, live: true },
  feed: [
    { time: "2h", text: "Sarah proposed a trade: D. Moore for J. Jacobs" },
    { time: "1d", text: "Waiver wire: Priya picked up R. Odunze" },
    { time: "2d", text: "Week 3 lineups locked" },
  ],
  ledgerHistory: [
    { week: "Week 1", you: 8, note: "1st place weekly high score" },
    { week: "Week 2", you: -5, note: "3rd place" },
    { week: "Week 3", you: 8, note: "1st place weekly high score" },
  ],
  draftBoard: {
    teams: ["You", "Mike", "Sarah", "Priya"],
    rounds: 8,
    picks: buildSnakeDraft(
      ["You", "Mike", "Sarah", "Priya"],
      [
        ["QB", ["J. Allen", "T. Marsh", "C. Wexler", "A. Renner"]],
        ["RB", ["B. Robinson", "D. Alvarez", "P. Nakamura", "T. Cabral"]],
        ["RB", ["D. Henry", "K. Whitfield", "J. Colton", "B. Lindgren"]],
        ["WR", ["A. St. Brown", "N. Boykins", "R. Beaumont", "H. Okonkwo"]],
        ["WR", ["D. Adams", "S. Fitch", "D. Iheanacho", "J. Beaulieu"]],
        ["TE", ["T. Kelce", "G. Castellanos", "M. Slattery", "V. Marchetti"]],
        ["FLEX", ["C. Lamb", "L. Odom", "E. Voss", "C. Duvall"]],
        ["DEF", ["Ravens", "Bears", "Steelers", "Broncos"]],
      ],
    ),
  },
};

const officePool: League = {
  id: "office-pool",
  name: "Office Pool",
  season: "2026 · Week 3 of 17",
  buyIn: 20,
  potTotal: 180,
  standings: [
    { name: "You", pts: 98.4, rank: 3, w: 1, l: 2 },
    { name: "Chris", pts: 118.9, rank: 1, w: 3, l: 0 },
    { name: "Ana", pts: 112.0, rank: 2, w: 2, l: 1 },
    { name: "Deion", pts: 90.1, rank: 4, w: 1, l: 2 },
    { name: "Wes", pts: 84.6, rank: 5, w: 0, l: 3 },
  ],
  myRoster: [],
  matchup: { opp: "Deion", myScore: 98.4, oppScore: 90.1, myProj: 101.0, oppProj: 95.4, live: false },
  feed: [{ time: "5h", text: "Chris takes sole possession of first place" }],
  ledgerHistory: [
    { week: "Week 1", you: -10, note: "4th place" },
    { week: "Week 2", you: -10, note: "5th place" },
    { week: "Week 3", you: 15, note: "2nd place, close win" },
  ],
};

/**
 * Builds a standard 4-team snake draft (round order reverses every other
 * round) from a fixed per-round position + per-team player list. Pure and
 * deterministic — this is historical record data, not something a user
 * edits, so it's generated once here rather than hand-numbering 32 picks.
 */
function buildSnakeDraft(teams: string[], rounds: [string, string[]][]): DraftPick[] {
  const picks: DraftPick[] = [];
  let overall = 1;
  rounds.forEach(([pos, playersByTeam], roundIdx) => {
    const round = roundIdx + 1;
    const order = round % 2 === 1 ? teams : [...teams].reverse();
    order.forEach((team, i) => {
      const teamIdx = teams.indexOf(team);
      picks.push({
        overallPick: overall++,
        round,
        pickInRound: i + 1,
        team,
        pos,
        player: playersByTeam[teamIdx],
      });
    });
  });
  return picks;
}

export const fantasySeed: FantasyData = {
  leagues: [sundayGuys, officePool],
  activeLeagueId: sundayGuys.id,
};

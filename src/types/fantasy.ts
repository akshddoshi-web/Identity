export interface Standing {
  name: string;
  pts: number;
  rank: number;
  w: number;
  l: number;
}

export interface RosterEntry {
  pos: string;
  name: string;
  pts: number;
  proj: number;
  salary: number;
}

export interface Matchup {
  opp: string;
  myScore: number;
  oppScore: number;
  myProj: number;
  oppProj: number;
  live: boolean;
}

export interface FeedItem {
  time: string;
  text: string;
}

export interface LedgerEntry {
  week: string;
  you: number;
  note: string;
}

export interface DraftPick {
  overallPick: number;
  round: number;
  pickInRound: number;
  team: string;
  player: string;
  pos: string;
}

export interface DraftBoard {
  teams: string[];
  rounds: number;
  picks: DraftPick[];
}

export interface League {
  id: string;
  name: string;
  season: string;
  buyIn: number;
  potTotal: number;
  standings: Standing[];
  myRoster: RosterEntry[];
  matchup: Matchup;
  feed: FeedItem[];
  ledgerHistory: LedgerEntry[];
  /** Undefined where the demo has no draft record for this league — same
   *  "no data yet" pattern as an empty myRoster. */
  draftBoard?: DraftBoard;
}

export interface FantasyData {
  leagues: League[];
  activeLeagueId: string;
}

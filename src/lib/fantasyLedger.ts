// Turns a league's final standings into a zero-sum settle-up ledger, so
// src/lib/settleUp.ts (which knows nothing about fantasy football) has
// something to work with. Kept separate from settleUp.ts on purpose — this
// is the one place that knows what "payout" means for a fantasy pool.
import type { Balance } from "./settleUp";
import type { League } from "@/types/fantasy";

// Standard top-heavy payout structure: only the top 3 places get paid.
const PAYOUT_PCT_BY_RANK = [0.6, 0.3, 0.1];

export function payoutForRank(rank: number, pot: number): number {
  const pct = PAYOUT_PCT_BY_RANK[rank - 1] ?? 0;
  return pct * pot;
}

/**
 * Each participant's net position (payout received minus their fair share
 * of the pot). Uses potTotal / participant count as the fair share rather
 * than the league's seeded `buyIn` field — in the seed data those don't
 * always agree (Office Pool: $20 buy-in but a $180 pot for 5 people, which
 * isn't $20 x 5), and deriving the share from the pot itself guarantees
 * this is zero-sum, which settleUp() requires.
 */
export function buildLeagueBalances(league: League): Balance[] {
  const n = league.standings.length;
  if (n === 0) return [];
  const fairShare = league.potTotal / n;

  return league.standings.map((s) => ({
    who: s.name,
    amount: payoutForRank(s.rank, league.potTotal) - fairShare,
  }));
}

/** Balances across every league the user is in, ready for settleUp(). */
export function buildCombinedBalances(leagues: League[]): Balance[] {
  return leagues.flatMap(buildLeagueBalances);
}

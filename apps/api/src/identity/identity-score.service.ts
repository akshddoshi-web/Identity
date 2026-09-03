import { Injectable } from "@nestjs/common";
import type { IdentityThread } from "@prisma/client";
import type { ThreadScore } from "@identity/shared";

/**
 * Computes the rolling 30-day trend score per thread and the composite Identity Score.
 *
 * Phase 0 ships no pillar data yet (nutrition/finance/schedule/fantasy land in Phases
 * 1-3), so every thread starts flat at 0 with no trend. From Phase 1 onward this
 * service is extended to pull thread-tagged actions (meals, transactions, schedule
 * adherence, roster moves) from the last 30 days and turn them into a 0-100 score
 * per thread, weighted into the composite by IdentityThread.weight.
 */
@Injectable()
export class IdentityScoreService {
  computeZeroStateScores(threads: IdentityThread[]): ThreadScore[] {
    return threads.map((thread) => ({
      threadId: thread.id,
      label: thread.label,
      score: 0,
      trend: 0,
    }));
  }

  computeComposite(threads: IdentityThread[], threadScores: ThreadScore[]): number {
    if (threads.length === 0) return 0;
    const weightSum = threads.reduce((sum, t) => sum + t.weight, 0) || 1;
    const scoreById = new Map(threadScores.map((s) => [s.threadId, s.score]));
    const weighted = threads.reduce((sum, t) => sum + (t.weight / weightSum) * (scoreById.get(t.id) ?? 0), 0);
    return Math.round(weighted);
  }
}

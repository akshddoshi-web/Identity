/**
 * Core entity shapes shared between the API and mobile client.
 * These mirror (a subset of) the Prisma models in apps/api/prisma/schema.prisma.
 * Phase 0 only defines the identity core: User, IdentityThread, IdentityScoreSnapshot.
 * Later phases add Finance/Nutrition/Fantasy/Schedule shapes here as those modules land.
 */

export const PILLARS = ["finance", "nutrition", "schedule", "fantasy"] as const;
export type Pillar = (typeof PILLARS)[number];

export interface User {
  id: string;
  email: string;
  name: string | null;
  timezone: string;
  createdAt: string;
}

export interface IdentityThread {
  id: string;
  userId: string;
  label: string;
  description: string | null;
  /** Relative weight of this thread in the composite Identity Score, 0-1, all threads sum to 1 */
  weight: number;
  createdAt: string;
}

/** A thread's rolling 30-day trend score, 0-100 */
export interface ThreadScore {
  threadId: string;
  label: string;
  score: number;
  /** delta vs previous snapshot, for the "living thing that moves" UI */
  trend: number;
}

export interface IdentityScoreSnapshot {
  id: string;
  userId: string;
  date: string;
  compositeScore: number;
  threadScores: ThreadScore[];
}

export interface DashboardResponse {
  user: Pick<User, "id" | "name" | "email">;
  threads: IdentityThread[];
  latestSnapshot: IdentityScoreSnapshot | null;
  /** true until the user has logged enough real activity for a non-zero score */
  isZeroState: boolean;
}

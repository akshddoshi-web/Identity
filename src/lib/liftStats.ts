// Pure functions that derive every display stat (last session, 3-week
// trend, PR, sparkline, training volume, streaks) from a lift's real
// set-by-set log — nothing here is a separately-authored summary field.
import type { Lift, SetEntry, TrainingSlot, WorkoutSession } from "@/types/fitness";

const WINDOW = 10; // the 10 most recent weekly sessions, matching the prototype's 10-point sparkline

export interface TopSet {
  date: string;
  weight: number;
  reps: number;
}

function topSetOf(session: WorkoutSession): TopSet {
  const best = [...session.sets].sort((a, b) => b.weight - a.weight || b.reps - a.reps)[0];
  return { date: session.date, weight: best.weight, reps: best.reps };
}

/** The most recent `WINDOW` sessions, oldest first — drops the older
 *  all-time-PR-only session that sits before the regular weekly window. */
export function windowedSessions(sessions: WorkoutSession[], window = WINDOW): WorkoutSession[] {
  return sessions.slice(-window);
}

/** The heaviest set ever logged for this lift (any session, any week). */
export function bestSetEver(sessions: WorkoutSession[]): TopSet | null {
  if (sessions.length === 0) return null;
  return sessions
    .map(topSetOf)
    .sort((a, b) => b.weight - a.weight || b.reps - a.reps)[0];
}

export function sessionTopSets(sessions: WorkoutSession[], window = WINDOW): TopSet[] {
  return windowedSessions(sessions, window).map(topSetOf);
}

export function lastSessionSummary(sessions: WorkoutSession[]): TopSet | null {
  const windowed = windowedSessions(sessions);
  return windowed.length ? topSetOf(windowed[windowed.length - 1]) : null;
}

export interface Trend {
  diffLb: number;
  label: string;
  up: boolean;
}

/** Compares the latest windowed session's top weight against the one
 *  `back` sessions earlier (default 3 — one session/week in this data, so
 *  "3 sessions back" reads as "3 weeks back"). */
export function trendOverSessions(sessions: WorkoutSession[], back = 3): Trend | null {
  const tops = sessionTopSets(sessions);
  if (tops.length <= back) return null;
  const latest = tops[tops.length - 1].weight;
  const earlier = tops[tops.length - 1 - back].weight;
  const diffLb = latest - earlier;
  return {
    diffLb,
    label: diffLb === 0 ? `flat / ${back}wk` : `${diffLb > 0 ? "+" : ""}${diffLb} lb / ${back}wk`,
    up: diffLb > 0,
  };
}

export function sparklineWeights(sessions: WorkoutSession[]): number[] {
  return sessionTopSets(sessions).map((t) => t.weight);
}

export interface PrEvent {
  date: string;
  weight: number;
  reps: number;
}

/**
 * "Working-set" PRs — a new best weight at this lift's normal rep scheme,
 * tracked separately from the all-time 1RM single (a different record
 * category: heaviest single vs. heaviest top set at working reps). Scans
 * the charted window chronologically; the first session is the baseline,
 * not a "new" PR.
 */
export function detectWorkingSetPRs(sessions: WorkoutSession[]): PrEvent[] {
  const tops = sessionTopSets(sessions);
  const events: PrEvent[] = [];
  let max = -Infinity;
  tops.forEach((t, i) => {
    if (i > 0 && t.weight > max) {
      events.push({ date: t.date, weight: t.weight, reps: t.reps });
    }
    max = Math.max(max, t.weight);
  });
  return events;
}

export function setVolume(set: SetEntry): number {
  return set.weight * set.reps;
}

export function sessionVolume(session: WorkoutSession): number {
  return session.sets.reduce((s, set) => s + setVolume(set), 0);
}

export interface WeeklyMuscleVolume {
  weekIndex: number;
  date: string;
  group: string;
  volume: number;
}

/**
 * Sum of weight x reps per muscle group per week. Bucketed by each lift's
 * session *index* within its windowed 10-session log rather than by
 * calendar ISO week — the seed data logs exactly one session per lift per
 * week by construction, so index position IS the week; a dataset with
 * irregular multi-session weeks would need real calendar-week bucketing.
 */
export function weeklyVolumeByMuscleGroup(lifts: Lift[], window = WINDOW): WeeklyMuscleVolume[] {
  const out: WeeklyMuscleVolume[] = [];
  for (const lift of lifts) {
    const windowed = windowedSessions(lift.sessions, window);
    windowed.forEach((session, weekIndex) => {
      out.push({ weekIndex, date: session.date, group: lift.muscleGroup, volume: sessionVolume(session) });
    });
  }
  return out;
}

export interface WeekCompletion {
  weekIndex: number;
  date: string;
  completedSlots: number;
  plannedSlots: number;
}

const SLOTS: TrainingSlot[] = ["Push", "Legs", "Pull"];

/**
 * Per week, how many of the 3 planned training slots (Push/Legs/Pull) got
 * a real session — "real" meaning 2+ sets, not just a single rushed set.
 * A slot with more than one lift (Push: Bench + OHP) counts as done if
 * either lift got a full session that week.
 */
export function weeklyCompletion(lifts: Lift[], window = WINDOW): WeekCompletion[] {
  const windowedBySlot = new Map<TrainingSlot, WorkoutSession[][]>();
  for (const slot of SLOTS) {
    windowedBySlot.set(
      slot,
      lifts.filter((l) => l.slot === slot).map((l) => windowedSessions(l.sessions, window)),
    );
  }

  const weeks: WeekCompletion[] = [];
  for (let w = 0; w < window; w++) {
    let completed = 0;
    let anyDate = "";
    for (const slot of SLOTS) {
      const liftsSessions = windowedBySlot.get(slot) ?? [];
      const full = liftsSessions.some((sessions) => {
        const s = sessions[w];
        if (s && !anyDate) anyDate = s.date;
        return s && s.sets.length >= 2;
      });
      if (full) completed++;
    }
    weeks.push({ weekIndex: w, date: anyDate, completedSlots: completed, plannedSlots: SLOTS.length });
  }
  return weeks;
}

export function currentWeekCompletion(lifts: Lift[]): WeekCompletion | null {
  const weeks = weeklyCompletion(lifts);
  return weeks.length ? weeks[weeks.length - 1] : null;
}

export interface StreakEvent {
  date: string;
  label: string;
  kind: "streak" | "broken";
}

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] ?? s[v] ?? s[0]);
}

/** Streak milestones reached (every 3rd consecutive full week) or broken,
 *  derived from the same weekly completion data as the accountability
 *  check — not a separate log. */
export function streakMilestones(lifts: Lift[]): StreakEvent[] {
  const weeks = weeklyCompletion(lifts);
  const events: StreakEvent[] = [];
  let streak = 0;

  for (const week of weeks) {
    const full = week.completedSlots === week.plannedSlots;
    if (full) {
      streak++;
      if (streak >= 3 && streak % 3 === 0) {
        events.push({
          date: week.date,
          label: `${ordinal(streak)} consecutive week completing the full Push/Legs/Pull split`,
          kind: "streak",
        });
      }
    } else {
      if (streak >= 2) {
        events.push({
          date: week.date,
          label: `Streak ended at ${streak} weeks — ${week.completedSlots}/${week.plannedSlots} planned days this week`,
          kind: "broken",
        });
      }
      streak = 0;
    }
  }
  return events;
}

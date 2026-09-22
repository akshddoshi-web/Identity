import type { FitnessData, Lift, WorkoutSession } from "@/types/fitness";

// Same reference "today" used by the Stocks and Fantasy seed data (Sep 2026).
const TODAY = new Date("2026-09-22T00:00:00");

function iso(daysAgo: number): string {
  const d = new Date(TODAY);
  d.setDate(d.getDate() - daysAgo);
  return d.toISOString().slice(0, 10);
}

/**
 * Builds 10 weekly sessions (oldest first) plus one older all-time 1RM
 * single, from just a weekly top-weight array — the same array the
 * prototype used for its sparkline. Every "collapsed stat" the prototype
 * showed (last session, 3-week trend, PR) is derived from this real
 * set-by-set log in src/lib/liftStats.ts, not stored redundantly here.
 *
 * `weekDaysAgo(i)` gives the day this lift's slot lands on in week `i`
 * (0 = oldest of the 10 charted weeks); `shortWeeks` marks weeks logged
 * with only the top single (a cut-short session), not a full 3-set session
 * — that's the real signal src/lib/fitnessInsights.ts reads for workout
 * completion.
 */
function buildSessions(
  weeklyTopWeights: number[],
  reps: number,
  weekDaysAgo: (i: number) => number,
  prWeight: number,
  prReps: number,
  shortWeeks: number[] = [],
): WorkoutSession[] {
  const prDaysAgo = weekDaysAgo(0) + 21; // 3 weeks before the oldest charted week
  const sessions: WorkoutSession[] = [{ date: iso(prDaysAgo), sets: [{ weight: prWeight, reps: prReps, rpe: 10 }] }];

  weeklyTopWeights.forEach((top, i) => {
    const date = iso(weekDaysAgo(i));
    if (shortWeeks.includes(i)) {
      sessions.push({ date, sets: [{ weight: top, reps, rpe: 9 }] });
    } else {
      sessions.push({
        date,
        sets: [
          { weight: top - 10, reps, rpe: 6 },
          { weight: top - 5, reps, rpe: 7 },
          { weight: top, reps, rpe: 8 },
        ],
      });
    }
  });

  return sessions;
}

// Each week's Push/Legs/Pull day, most recent week ending today. Bench and
// OHP share the Push day (OHP is a secondary lift layered on top of it, not
// its own completion slot — see TrainingSlot in types/fitness.ts).
const pullDaysAgo = (i: number) => (9 - i) * 7;
const legsDaysAgo = (i: number) => pullDaysAgo(i) + 2;
const pushDaysAgo = (i: number) => pullDaysAgo(i) + 4;

const lifts: Lift[] = [
  {
    id: "bench-press",
    name: "Bench Press",
    muscleGroup: "Chest",
    slot: "Push",
    sessions: buildSessions([165, 170, 170, 175, 175, 180, 180, 185, 185, 185], 5, pushDaysAgo, 205, 1),
  },
  {
    id: "squat",
    name: "Squat",
    muscleGroup: "Legs",
    slot: "Legs",
    sessions: buildSessions([220, 225, 225, 230, 235, 235, 240, 240, 245, 245], 5, legsDaysAgo, 275, 1),
  },
  {
    id: "deadlift",
    name: "Deadlift",
    muscleGroup: "Back",
    slot: "Pull",
    // Weeks 3 and 9 (the most recent week) are cut short — a single top
    // set instead of the usual 3. Week 9 is what the live accountability
    // check on Today actually sees; week 3 shows up as a broken streak in
    // the Progress tab's personal history.
    sessions: buildSessions([290, 295, 295, 290, 295, 295, 290, 295, 295, 295], 3, pullDaysAgo, 315, 1, [3, 9]),
  },
  {
    id: "ohp",
    name: "Overhead Press",
    muscleGroup: "Shoulders",
    slot: "Push",
    sessions: buildSessions([90, 90, 95, 95, 95, 100, 100, 105, 105, 105], 6, pushDaysAgo, 120, 1),
  },
];

export const fitnessSeed: FitnessData = {
  macros: {
    cal: { cur: 1780, goal: 2200 },
    protein: { cur: 142, goal: 170 },
    carbs: { cur: 165, goal: 220 },
    fat: { cur: 58, goal: 70 },
  },
  exerciseCal: 340,
  mealsToday: [
    {
      name: "Breakfast",
      items: [
        { name: "Oats (80g)", kcal: 304, protein: 10, carbs: 54, fat: 6 },
        { name: "Whey protein (1 scoop)", kcal: 120, protein: 24, carbs: 3, fat: 1.5 },
        { name: "Banana", kcal: 105, protein: 1, carbs: 27, fat: 0.4 },
      ],
    },
    {
      name: "Lunch",
      items: [
        { name: "Chicken breast (200g)", kcal: 330, protein: 62, carbs: 0, fat: 7 },
        { name: "White rice (150g)", kcal: 195, protein: 4, carbs: 43, fat: 0.4 },
        { name: "Broccoli (100g)", kcal: 34, protein: 3, carbs: 7, fat: 0.4 },
      ],
    },
    {
      name: "Dinner (logged so far)",
      items: [
        { name: "Ground beef 90/10 (150g)", kcal: 270, protein: 27, carbs: 0, fat: 18 },
        { name: "Sweet potato (200g)", kcal: 180, protein: 4, carbs: 41, fat: 0.2 },
      ],
    },
  ],
  micronutrients: [
    { name: "Fiber", current: "22g", reference: "38g" },
    { name: "Sugar", current: "54g", reference: "< 50g" },
    { name: "Sodium", current: "2,150mg", reference: "< 2,300mg" },
    { name: "Potassium", current: "2,840mg", reference: "3,400mg" },
    { name: "Vitamin C", current: "68mg", reference: "90mg" },
    { name: "Iron", current: "14mg", reference: "18mg" },
    { name: "Calcium", current: "820mg", reference: "1,000mg" },
    { name: "Cholesterol", current: "310mg", reference: "< 300mg" },
  ],
  lifts,
  split: {
    Mon: "Push (chest/shoulders/triceps)",
    Tue: "Pull (back/biceps)",
    Wed: "Legs",
    Thu: "Rest / cardio",
    Fri: "Push",
    Sat: "Pull",
    Sun: "Rest",
  },
  bodyweightHistory: [178.2, 178.0, 177.6, 177.8, 177.1, 176.9, 176.4, 176.5, 176.0, 175.6].map((weight, i) => ({
    weight,
    date: iso((9 - i) * 7),
  })),
  loggingStreakDays: 12,
};

export interface MacroTarget {
  cur: number;
  goal: number;
}

export interface Macros {
  cal: MacroTarget;
  protein: MacroTarget;
  carbs: MacroTarget;
  fat: MacroTarget;
}

export interface MealItem {
  name: string;
  kcal: number;
  protein: number;
  carbs: number;
  fat: number;
}

export interface Meal {
  name: string;
  items: MealItem[];
}

export interface Micronutrient {
  name: string;
  current: string;
  reference: string;
}

export type Weekday = "Mon" | "Tue" | "Wed" | "Thu" | "Fri" | "Sat" | "Sun";
export type SplitPlan = Record<Weekday, string>;

export interface SetEntry {
  weight: number;
  reps: number;
  rpe?: number;
}

export interface WorkoutSession {
  date: string; // ISO yyyy-mm-dd
  sets: SetEntry[];
}

/** One of the three planned training slots per week (Push/Legs/Pull) that
 *  the accountability engine checks completion against. */
export type TrainingSlot = "Push" | "Legs" | "Pull";

export interface Lift {
  id: string;
  name: string;
  muscleGroup: string;
  slot: TrainingSlot;
  /** Chronological, oldest first. The earliest entry is an all-time 1RM
   *  attempt well before the regular weekly window — see liftStats.ts. */
  sessions: WorkoutSession[];
}

export interface BodyweightEntry {
  date: string;
  weight: number;
}

export interface FitnessData {
  macros: Macros;
  exerciseCal: number;
  mealsToday: Meal[];
  micronutrients: Micronutrient[];
  lifts: Lift[];
  split: SplitPlan;
  bodyweightHistory: BodyweightEntry[];
  loggingStreakDays: number;
}

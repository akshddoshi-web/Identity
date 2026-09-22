export type Weekday = "Mon" | "Tue" | "Wed" | "Thu" | "Fri" | "Sat" | "Sun";
export type Category = "Academic" | "Work" | "Club" | "Personal" | "Fitness";

export interface PlannerBlock {
  id: string;
  text: string;
  done: boolean;
  cat: Category;
  /** 24h "HH:MM" — the prototype's blocks carry no time of day; these were
   *  authored fresh so the time-grid view has something real to lay out.
   *  See plannerSeed.ts. */
  start: string;
  end: string;
}

export type WeekPlan = Record<Weekday, PlannerBlock[]>;

export interface Milestone {
  label: string;
  done: boolean;
}

export interface LongGoal {
  id: string;
  name: string;
  deadline: string;
  milestones: Milestone[];
}

export interface PlannerData {
  week: WeekPlan;
  goals: LongGoal[];
  catColors: Record<Category, string>;
}

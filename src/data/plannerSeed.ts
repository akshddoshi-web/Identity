import type { Category, PlannerBlock, PlannerData } from "@/types/planner";

function block(id: string, text: string, done: boolean, cat: Category, start: string, end: string): PlannerBlock {
  return { id, text, done, cat, start, end };
}

// Every block's text/done/category is ported exactly from the prototype's
// plannerData. start/end times are new (see types/planner.ts) — authored
// per block so the time-grid view has real data to lay out, from the same
// underlying blocks the list view already used.
export const plannerSeed: PlannerData = {
  week: {
    Mon: [
      block("mon-cs230", "CS 230 Lecture", true, "Academic", "09:00", "10:15"),
      block("mon-standup", "Internship standup", true, "Work", "10:30", "10:45"),
      block("mon-gym", "Gym — Push", true, "Fitness", "17:00", "18:15"),
    ],
    Tue: [
      block("tue-linalg", "Linear Algebra HW", true, "Academic", "14:00", "15:30"),
      block("tue-club", "Club: Investing Society", false, "Club", "18:00", "19:00"),
    ],
    Wed: [
      block("wed-cs230", "CS 230 Lecture", false, "Academic", "09:00", "10:15"),
      block("wed-metrichub", "MetricHub sprint work", false, "Work", "13:00", "15:00"),
      block("wed-gym", "Gym — Pull", false, "Fitness", "17:00", "18:15"),
    ],
    Thu: [
      block("thu-history", "History reading", false, "Academic", "11:00", "12:30"),
      block("thu-resume", "Resume review — BCI app", false, "Personal", "15:00", "16:00"),
    ],
    Fri: [
      block("fri-demo", "Internship demo", false, "Work", "10:00", "11:00"),
      block("fri-gym", "Gym — Legs", false, "Fitness", "17:00", "18:15"),
    ],
    Sat: [
      block("sat-mealprep", "Meal prep", false, "Personal", "11:00", "12:30"),
      block("sat-fantasy", "Fantasy lineup lock 1pm", false, "Personal", "12:45", "13:00"),
    ],
    Sun: [
      block("sun-budget", "Weekly budget review", false, "Personal", "10:00", "10:45"),
      block("sun-rest", "Rest / plan next week", false, "Personal", "20:00", "20:30"),
    ],
  },
  goals: [
    {
      id: "swe-offer",
      name: "Land a full-time SWE offer",
      deadline: "Spring 2027",
      milestones: [
        { label: "Update resume", done: true },
        { label: "Apply to BCI / finance-adjacent roles", done: true },
        { label: "Finish 2 more DSA sets", done: false },
        { label: "Mock interview w/ a friend", done: false },
      ],
    },
    {
      id: "ce-degree",
      name: "Finish CE degree requirements",
      deadline: "May 2027",
      milestones: [
        { label: "Pass ECE 371 (Info Security)", done: false },
        { label: "Complete linear algebra", done: false },
        { label: "Confirm remaining major electives", done: true },
      ],
    },
  ],
  catColors: {
    Academic: "var(--blue)",
    Work: "var(--orange)",
    Club: "var(--purple)",
    Personal: "var(--accent)",
    Fitness: "var(--pink)",
  },
};

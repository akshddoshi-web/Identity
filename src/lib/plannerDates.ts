import type { Weekday } from "@/types/planner";

// Same reference "today" as the other seeds (Stocks, Fantasy, Fitness).
const TODAY = new Date("2026-09-22T00:00:00");

export const WEEKDAYS: Weekday[] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function weekdayLabel(date: Date): Weekday {
  return date.toLocaleDateString("en-US", { weekday: "short" }) as Weekday;
}

export const TODAY_WEEKDAY: Weekday = weekdayLabel(TODAY);

export const TOMORROW_WEEKDAY: Weekday = (() => {
  const idx = WEEKDAYS.indexOf(TODAY_WEEKDAY);
  return WEEKDAYS[(idx + 1) % WEEKDAYS.length];
})();

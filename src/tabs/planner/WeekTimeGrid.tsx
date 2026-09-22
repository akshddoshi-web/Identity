import { WEEKDAYS, TODAY_WEEKDAY } from "@/lib/plannerDates";
import { usePlannerStore } from "@/store/usePlannerStore";
import { PlannerBlockRow } from "./PlannerBlockRow";
import { clsx } from "@/lib/clsx";

const GRID_START_MIN = 8 * 60; // 08:00
const GRID_END_MIN = 21 * 60; // 21:00
const GRID_SPAN_MIN = GRID_END_MIN - GRID_START_MIN;
const HOUR_ROWS = Array.from({ length: (GRID_END_MIN - GRID_START_MIN) / 60 }, (_, i) => GRID_START_MIN / 60 + i);

function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

function formatHour(hour: number): string {
  const h12 = hour % 12 === 0 ? 12 : hour % 12;
  return `${h12}${hour < 12 ? "am" : "pm"}`;
}

export function WeekTimeGrid() {
  const week = usePlannerStore((s) => s.week);
  const catColors = usePlannerStore((s) => s.catColors);
  const rowHeight = 44; // px per hour

  return (
    <div className="scrollbar-thin overflow-x-auto border border-border">
      <div className="grid min-w-[820px] grid-cols-[56px_repeat(7,1fr)]">
        <div className="border-b border-r border-border" />
        {WEEKDAYS.map((day) => (
          <div
            key={day}
            className={clsx(
              "border-b border-r border-border py-2 text-center font-mono text-[11px] font-bold uppercase tracking-wide last:border-r-0",
              day === TODAY_WEEKDAY && "bg-panel3",
            )}
          >
            {day}
          </div>
        ))}

        <div className="border-r border-border" style={{ height: HOUR_ROWS.length * rowHeight }}>
          {HOUR_ROWS.map((hour) => (
            <div
              key={hour}
              className="border-t border-border pr-1.5 text-right font-mono text-[9.5px] text-sub first:border-t-0"
              style={{ height: rowHeight }}
            >
              {formatHour(hour)}
            </div>
          ))}
        </div>

        {WEEKDAYS.map((day) => (
          <div
            key={day}
            className={clsx("relative border-r border-border last:border-r-0", day === TODAY_WEEKDAY && "bg-panel2")}
            style={{ height: HOUR_ROWS.length * rowHeight }}
          >
            {HOUR_ROWS.map((hour, i) => (
              <div key={hour} className="absolute inset-x-0 border-t border-border" style={{ top: i * rowHeight }} />
            ))}
            {week[day].map((block) => {
              const start = Math.max(toMinutes(block.start), GRID_START_MIN);
              const end = Math.min(toMinutes(block.end), GRID_END_MIN);
              if (end <= start) return null;
              const top = ((start - GRID_START_MIN) / GRID_SPAN_MIN) * HOUR_ROWS.length * rowHeight;
              const height = ((end - start) / GRID_SPAN_MIN) * HOUR_ROWS.length * rowHeight;
              return (
                <div key={block.id} className="absolute inset-x-0.5" style={{ top, height: Math.max(height, 18) }}>
                  <PlannerBlockRow day={day} block={block} color={catColors[block.cat]} variant="grid" />
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

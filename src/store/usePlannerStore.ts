import { create } from "zustand";
import { persist } from "zustand/middleware";
import { plannerSeed } from "@/data/plannerSeed";
import type { PlannerData, Weekday } from "@/types/planner";

interface PlannerStore extends PlannerData {
  toggleBlockDone: (day: Weekday, blockId: string) => void;
  editBlockText: (day: Weekday, blockId: string, text: string) => void;
  /** Explicit "plan tomorrow" actions — never automatic. */
  moveBlockToTomorrow: (day: Weekday, blockId: string, tomorrow: Weekday) => void;
  dropBlock: (day: Weekday, blockId: string) => void;
  resetToSeed: () => void;
}

export const usePlannerStore = create<PlannerStore>()(
  persist(
    (set) => ({
      ...plannerSeed,

      toggleBlockDone: (day, blockId) =>
        set((state) => ({
          week: {
            ...state.week,
            [day]: state.week[day].map((b) => (b.id === blockId ? { ...b, done: !b.done } : b)),
          },
        })),

      editBlockText: (day, blockId, text) =>
        set((state) => ({
          week: {
            ...state.week,
            [day]: state.week[day].map((b) => (b.id === blockId ? { ...b, text } : b)),
          },
        })),

      moveBlockToTomorrow: (day, blockId, tomorrow) =>
        set((state) => {
          const moving = state.week[day].find((b) => b.id === blockId);
          if (!moving) return state;
          return {
            week: {
              ...state.week,
              [day]: state.week[day].filter((b) => b.id !== blockId),
              [tomorrow]: [...state.week[tomorrow], moving],
            },
          };
        }),

      dropBlock: (day, blockId) =>
        set((state) => ({
          week: { ...state.week, [day]: state.week[day].filter((b) => b.id !== blockId) },
        })),

      resetToSeed: () => set({ ...plannerSeed }),
    }),
    { name: "identity-planner-store" },
  ),
);

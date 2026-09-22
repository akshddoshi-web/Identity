import { create } from "zustand";
import { persist } from "zustand/middleware";
import { homeSeed } from "@/data/homeSeed";
import type { HomeData } from "@/types/domain";

interface HomeStore extends HomeData {
  cancelSubscription: (id: string) => void;
  toggleGoalContribution: (goalId: string, amount: number) => void;
  resetToSeed: () => void;
}

export const useHomeStore = create<HomeStore>()(
  persist(
    (set) => ({
      ...homeSeed,

      cancelSubscription: (id) =>
        set((state) => ({
          subscriptions: state.subscriptions.filter((s) => s.id !== id),
        })),

      toggleGoalContribution: (goalId, amount) =>
        set((state) => ({
          savingsGoals: state.savingsGoals.map((g) =>
            g.id === goalId ? { ...g, current: Math.max(0, Math.min(g.target, g.current + amount)) } : g,
          ),
        })),

      resetToSeed: () => set({ ...homeSeed }),
    }),
    { name: "identity-home-store" },
  ),
);

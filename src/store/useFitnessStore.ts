import { create } from "zustand";
import { persist } from "zustand/middleware";
import { fitnessSeed } from "@/data/fitnessSeed";
import type { FitnessData } from "@/types/fitness";

interface FitnessStore extends FitnessData {
  resetToSeed: () => void;
}

export const useFitnessStore = create<FitnessStore>()(
  persist(
    (set) => ({
      ...fitnessSeed,
      resetToSeed: () => set({ ...fitnessSeed }),
    }),
    { name: "identity-fitness-store" },
  ),
);

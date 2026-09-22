import { create } from "zustand";
import { persist } from "zustand/middleware";
import { fantasySeed } from "@/data/fantasySeed";
import type { FantasyData } from "@/types/fantasy";

interface FantasyStore extends FantasyData {
  setActiveLeague: (id: string) => void;
  resetToSeed: () => void;
}

export const useFantasyStore = create<FantasyStore>()(
  persist(
    (set) => ({
      ...fantasySeed,
      setActiveLeague: (id) => set({ activeLeagueId: id }),
      resetToSeed: () => set({ ...fantasySeed }),
    }),
    { name: "identity-fantasy-store" },
  ),
);

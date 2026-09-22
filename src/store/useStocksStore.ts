import { create } from "zustand";
import { persist } from "zustand/middleware";
import { stocksSeed } from "@/data/stocksSeed";
import type { StocksData } from "@/types/stocks";

interface StocksStore extends StocksData {
  resetToSeed: () => void;
}

export const useStocksStore = create<StocksStore>()(
  persist(
    (set) => ({
      ...stocksSeed,
      resetToSeed: () => set({ ...stocksSeed }),
    }),
    { name: "identity-stocks-store" },
  ),
);

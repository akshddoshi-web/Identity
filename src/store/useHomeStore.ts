import { create } from "zustand";
import { persist } from "zustand/middleware";
import { homeSeed } from "@/data/homeSeed";
import type { Account, HomeData, Transaction } from "@/types/domain";

interface HomeStore extends HomeData {
  cancelSubscription: (id: string) => void;
  toggleGoalContribution: (goalId: string, amount: number) => void;
  resetToSeed: () => void;
  /** Adds a newly-linked (real, sandbox) Plaid account + its transactions
   *  alongside whatever's already here — seed data included. Re-linking
   *  the same Item replaces its accounts/transactions by id rather than
   *  duplicating them; nothing else is touched (see README, Stage 7). */
  addPlaidData: (accounts: Account[], transactions: Transaction[]) => void;
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

      addPlaidData: (accounts, transactions) =>
        set((state) => {
          const newAccountIds = new Set(accounts.map((a) => a.id));
          const newTxIds = new Set(transactions.map((t) => t.id));
          return {
            accounts: [...state.accounts.filter((a) => !newAccountIds.has(a.id)), ...accounts],
            transactions: [...state.transactions.filter((t) => !newTxIds.has(t.id)), ...transactions],
          };
        }),
    }),
    { name: "identity-home-store" },
  ),
);

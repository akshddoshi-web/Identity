export interface TabConfig {
  id: string;
  label: string;
  subs: string[];
}

export const TABS: TabConfig[] = [
  {
    id: "home",
    label: "HOME",
    subs: ["Insights", "Overview", "Accounts", "Transactions", "Budgets", "Goals"],
  },
  { id: "stocks", label: "STOCKS", subs: ["Portfolio", "Watchlist", "Insights"] },
  { id: "fantasy", label: "FANTASY", subs: ["Lobby", "Matchup", "My Team", "Ledger"] },
  { id: "fitness", label: "FITNESS", subs: ["Today", "Nutrients", "Lifts", "Progress"] },
  { id: "planner", label: "PLANNER", subs: ["Week", "Goals"] },
  // No sub-tabs on purpose: Status isn't organized into sections the way
  // every other tab is, it's one ranked list. AppShell/SubTabNav/
  // TabIndexRedirect all treat an empty subs[] as "this tab has no sub-tab
  // strip," not a bug to route around.
  { id: "status", label: "STATUS", subs: [] },
];

export function slugify(label: string): string {
  return label.toLowerCase().replace(/\s+/g, "-");
}

export function findTab(id: string): TabConfig | undefined {
  return TABS.find((t) => t.id === id);
}

import type { HomeData } from "@/types/domain";

// Mirrors the sample data from the original single-file prototype (index.html)
// exactly, with stable ids added for React keys / store lookups, and
// nextChargeDate added to subscriptions to drive the countdown UI.
export const homeSeed: HomeData = {
  accounts: [
    { id: "acc-checking", name: "Chase Total Checking", type: "Checking", last4: "4821", balance: 1840.22 },
    { id: "acc-cc", name: "Chase Sapphire Preferred", type: "Credit Card", last4: "7710", balance: -612.4 },
    { id: "acc-savings", name: "Marcus Online Savings", type: "Savings", last4: "0093", balance: 6250.0 },
    { id: "acc-invest", name: "Robinhood Brokerage", type: "Investing", last4: "2214", balance: 4980.15 },
  ],

  avenues: [
    {
      id: "ave-investing",
      name: "Investing",
      color: "var(--blue)",
      budget: 600,
      spent: 410,
      sub: [
        { label: "Auto-invest transfers", amount: 250 },
        { label: "Individual stock buys", amount: 160 },
      ],
    },
    {
      id: "ave-entertainment",
      name: "Entertainment",
      color: "var(--purple)",
      budget: 250,
      spent: 295,
      sub: [
        { label: "Bars/going out", amount: 146 },
        { label: "Games/Steam", amount: 60 },
        { label: "Streaming add-ons", amount: 89 },
      ],
    },
    {
      id: "ave-savings",
      name: "Savings",
      color: "var(--accent)",
      budget: 500,
      spent: 500,
      sub: [{ label: "Auto-transfer", amount: 500 }],
    },
    {
      id: "ave-fitness",
      name: "Fitness / Health",
      color: "var(--orange)",
      budget: 150,
      spent: 95,
      sub: [
        { label: "Gym membership", amount: 25 },
        { label: "Supplements", amount: 40 },
        { label: "Meal prep", amount: 30 },
      ],
    },
    {
      id: "ave-food",
      name: "Food",
      color: "var(--yellow)",
      budget: 400,
      spent: 378,
      sub: [
        { label: "Groceries", amount: 210 },
        { label: "Takeout", amount: 168 },
      ],
    },
    {
      id: "ave-subscriptions",
      name: "Subscriptions",
      color: "var(--red)",
      budget: 80,
      spent: 112,
      sub: [
        { label: "Spotify", amount: 11.99 },
        { label: "Netflix", amount: 15.49 },
        { label: "HBO Max", amount: 16.99 },
        { label: "Cursor", amount: 20 },
        { label: "Claude", amount: 20 },
        { label: "Gym app", amount: 8.99 },
        { label: "iCloud", amount: 2.99 },
        { label: "Other", amount: 15.54 },
      ],
    },
  ],

  monthlyTrend: [
    { month: "Apr", value: 1680 },
    { month: "May", value: 1820 },
    { month: "Jun", value: 1590 },
    { month: "Jul", value: 2010 },
    { month: "Aug", value: 1875 },
    { month: "Sep", value: 1790 },
  ],

  transactions: [
    { id: "tx-1", merchant: "Robinhood Transfer", cat: "Investing", amt: -200, date: "Sep 18" },
    { id: "tx-2", merchant: "Chipotle", cat: "Food", amt: -14.2, date: "Sep 18" },
    { id: "tx-3", merchant: "Steam", cat: "Entertainment", amt: -59.99, date: "Sep 17" },
    { id: "tx-4", merchant: "Spotify", cat: "Subscriptions", amt: -11.99, date: "Sep 16" },
    { id: "tx-5", merchant: "Netflix", cat: "Subscriptions", amt: -15.49, date: "Sep 16" },
    { id: "tx-6", merchant: "HBO Max", cat: "Subscriptions", amt: -16.99, date: "Sep 16" },
    { id: "tx-7", merchant: "Planet Fitness", cat: "Fitness / Health", amt: -24.99, date: "Sep 15" },
    { id: "tx-8", merchant: "Autosave → Savings", cat: "Savings", amt: -250, date: "Sep 15" },
    { id: "tx-9", merchant: "Bar tab", cat: "Entertainment", amt: -86.4, date: "Sep 14" },
    { id: "tx-10", merchant: "Whole Foods", cat: "Food", amt: -71.3, date: "Sep 13" },
    { id: "tx-11", merchant: "Trader Joe's", cat: "Food", amt: -48.9, date: "Sep 11" },
    { id: "tx-12", merchant: "Paycheck — Advantest", cat: "Income", amt: 2150.0, date: "Sep 10" },
    { id: "tx-13", merchant: "NVDA buy", cat: "Investing", amt: -160, date: "Sep 9" },
    { id: "tx-14", merchant: "Cursor subscription", cat: "Subscriptions", amt: -20, date: "Sep 8" },
    { id: "tx-15", merchant: "Claude subscription", cat: "Subscriptions", amt: -20, date: "Sep 8" },
  ],

  savingsGoals: [
    { id: "goal-emergency", name: "Emergency fund", target: 8000, current: 6250, deadline: "Dec 2026" },
    { id: "goal-montreal", name: "Montreal trip", target: 900, current: 640, deadline: "Oct 2026" },
    { id: "goal-laptop", name: "New laptop", target: 2200, current: 400, deadline: "Mar 2027" },
  ],

  netWorthHistory: [10120, 10340, 10580, 10290, 10710, 10940, 11180, 11340, 11510, 11620, 11780, 12070],

  subscriptions: [
    { id: "sub-netflix", name: "Netflix", cost: 15.49, cadence: "Monthly", lastUsed: "2 days ago", unused: false, nextChargeDate: "2026-10-16" },
    { id: "sub-hbomax", name: "HBO Max", cost: 16.99, cadence: "Monthly", lastUsed: "19 days ago", unused: true, nextChargeDate: "2026-10-16" },
    { id: "sub-spotify", name: "Spotify", cost: 11.99, cadence: "Monthly", lastUsed: "Today", unused: false, nextChargeDate: "2026-10-16" },
    { id: "sub-cursor", name: "Cursor", cost: 20, cadence: "Monthly", lastUsed: "1 day ago", unused: false, nextChargeDate: "2026-10-08" },
    { id: "sub-claude", name: "Claude", cost: 20, cadence: "Monthly", lastUsed: "Today", unused: false, nextChargeDate: "2026-10-08" },
    { id: "sub-gymapp", name: "Gym app add-on", cost: 8.99, cadence: "Monthly", lastUsed: "41 days ago", unused: true, nextChargeDate: "2026-09-24" },
    { id: "sub-icloud", name: "iCloud+", cost: 2.99, cadence: "Monthly", lastUsed: "Today", unused: false, nextChargeDate: "2026-09-28" },
  ],

  insights: [
    {
      id: "insight-subs-over-budget",
      tone: "crit",
      ico: "⚠",
      title: "Subscriptions are up $32/mo over budget",
      body: "You're paying for 7 subscriptions totaling $96.45/mo against an $80 budget. Two haven't been opened in over 2 weeks — HBO Max and your gym app add-on.",
      cta: "Review subscriptions",
    },
    {
      id: "insight-networth-up",
      tone: "money",
      ico: "↑",
      title: "Net worth is up 2.5% this month",
      body: "Driven mostly by your NVDA position and a steady autosave into Savings. Keep the autosave running — it's your single biggest net-worth lever right now.",
    },
    {
      id: "insight-entertainment-over",
      tone: "warn",
      ico: "◎",
      title: "Entertainment avenue is 18% over budget",
      body: "$295 spent against a $250 budget, mostly bar tabs. At this pace you'll close the month roughly $80 over.",
    },
    {
      id: "insight-big-transaction",
      tone: "warn",
      ico: "$",
      title: "Big transaction detected",
      body: "A $200 transfer to Robinhood on Sep 18 was 4x your typical investing transfer size. Flagged for visibility, not blocked.",
    },
  ],
};

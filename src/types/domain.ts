export interface Account {
  id: string;
  name: string;
  type: "Checking" | "Credit Card" | "Savings" | "Investing";
  last4: string;
  balance: number;
}

export interface AvenueSubItem {
  label: string;
  amount: number;
}

export interface Avenue {
  id: string;
  name: string;
  color: string;
  budget: number;
  spent: number;
  sub: AvenueSubItem[];
}

export interface MonthlyTrendPoint {
  month: string;
  value: number;
}

export type TransactionCategory = string;

export interface Transaction {
  id: string;
  merchant: string;
  cat: TransactionCategory;
  amt: number;
  date: string;
}

export interface SavingsGoal {
  id: string;
  name: string;
  target: number;
  current: number;
  deadline: string;
}

export interface Subscription {
  id: string;
  name: string;
  cost: number;
  cadence: "Monthly" | "Yearly";
  lastUsed: string;
  unused: boolean;
  nextChargeDate: string; // ISO date
}

export type InsightTone = "crit" | "warn" | "money" | "neutral";

export interface Insight {
  id: string;
  tone: InsightTone;
  ico: string;
  title: string;
  body: string;
  cta?: string;
}

export interface HomeData {
  accounts: Account[];
  avenues: Avenue[];
  monthlyTrend: MonthlyTrendPoint[];
  transactions: Transaction[];
  savingsGoals: SavingsGoal[];
  netWorthHistory: number[];
  subscriptions: Subscription[];
  insights: Insight[];
}

import { useParams } from "react-router-dom";
import { InsightsView } from "./InsightsView";
import { OverviewView } from "./OverviewView";
import { AccountsView } from "./AccountsView";
import { TransactionsView } from "./TransactionsView";
import { BudgetsView } from "./BudgetsView";
import { GoalsView } from "./GoalsView";

const VIEWS: Record<string, React.ComponentType> = {
  insights: InsightsView,
  overview: OverviewView,
  accounts: AccountsView,
  transactions: TransactionsView,
  budgets: BudgetsView,
  goals: GoalsView,
};

export function HomeTab() {
  const { subSlug = "insights" } = useParams();
  const View = VIEWS[subSlug] ?? InsightsView;
  return <View />;
}

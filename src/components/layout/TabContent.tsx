import { useParams } from "react-router-dom";
import { HomeTab } from "@/tabs/home/HomeTab";
import { StocksTab } from "@/tabs/stocks/StocksTab";
import { FantasyTab } from "@/tabs/fantasy/FantasyTab";
import { FitnessTab } from "@/tabs/fitness/FitnessTab";
import { PlannerTab } from "@/tabs/planner/PlannerTab";
import { ComingSoon } from "@/tabs/placeholder/ComingSoon";

export function TabContent() {
  const { tabId = "home" } = useParams();

  if (tabId === "home") return <HomeTab />;
  if (tabId === "stocks") return <StocksTab />;
  if (tabId === "fantasy") return <FantasyTab />;
  if (tabId === "fitness") return <FitnessTab />;
  if (tabId === "planner") return <PlannerTab />;
  // Unreachable through the nav (all 5 configured tabs are handled above);
  // kept as a fallback for a hand-typed/bogus tabId in the URL.
  return <ComingSoon />;
}

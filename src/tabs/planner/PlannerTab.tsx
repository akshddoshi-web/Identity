import { useParams } from "react-router-dom";
import { WeekView } from "./WeekView";
import { GoalsView } from "./GoalsView";
import { PlanTomorrowView } from "./PlanTomorrowView";

const VIEWS: Record<string, React.ComponentType> = {
  week: WeekView,
  goals: GoalsView,
};

export function PlannerTab() {
  const { subSlug = "week", detailId } = useParams();

  if (subSlug === "week" && detailId === "plan-tomorrow") {
    return <PlanTomorrowView />;
  }

  const View = VIEWS[subSlug] ?? WeekView;
  return <View />;
}

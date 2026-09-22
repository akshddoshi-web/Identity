import { useParams } from "react-router-dom";
import { TodayView } from "./TodayView";
import { NutrientsView } from "./NutrientsView";
import { LiftsView } from "./LiftsView";
import { LiftDetailView } from "./LiftDetailView";
import { ProgressView } from "./ProgressView";

const VIEWS: Record<string, React.ComponentType> = {
  today: TodayView,
  nutrients: NutrientsView,
  lifts: LiftsView,
  progress: ProgressView,
};

export function FitnessTab() {
  const { subSlug = "today", detailId } = useParams();

  if (subSlug === "lifts" && detailId) {
    return <LiftDetailView liftId={detailId} />;
  }

  const View = VIEWS[subSlug] ?? TodayView;
  return <View />;
}

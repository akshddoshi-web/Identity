import { Navigate, useParams } from "react-router-dom";
import { findTab, slugify } from "@/config/tabs";
import { TabContent } from "./TabContent";

export function TabIndexRedirect() {
  const { tabId = "home" } = useParams();
  const tab = findTab(tabId) ?? findTab("home")!;
  // A tab with no sub-tabs (Status) has nowhere to redirect to — render its
  // content directly at /:tabId instead of bouncing to /:tabId/undefined.
  if (tab.subs.length === 0) return <TabContent />;
  return <Navigate to={`/${tab.id}/${slugify(tab.subs[0])}`} replace />;
}

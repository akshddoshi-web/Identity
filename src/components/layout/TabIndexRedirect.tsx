import { Navigate, useParams } from "react-router-dom";
import { findTab, slugify } from "@/config/tabs";

export function TabIndexRedirect() {
  const { tabId = "home" } = useParams();
  const tab = findTab(tabId) ?? findTab("home")!;
  return <Navigate to={`/${tab.id}/${slugify(tab.subs[0])}`} replace />;
}

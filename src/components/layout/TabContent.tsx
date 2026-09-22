import { useParams } from "react-router-dom";
import { HomeTab } from "@/tabs/home/HomeTab";
import { ComingSoon } from "@/tabs/placeholder/ComingSoon";

export function TabContent() {
  const { tabId = "home" } = useParams();

  if (tabId === "home") return <HomeTab />;
  return <ComingSoon />;
}

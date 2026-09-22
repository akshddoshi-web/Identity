import { useParams } from "react-router-dom";
import { findTab } from "@/config/tabs";

export function ComingSoon() {
  const { tabId = "" } = useParams();
  const tab = findTab(tabId);

  return (
    <div className="flex flex-col items-center gap-2 border border-border py-24 text-center">
      <div className="font-mono text-xs uppercase tracking-[2px] text-sub">{tab?.label ?? tabId}</div>
      <div className="text-lg font-semibold">Coming soon</div>
      <div className="max-w-xs text-xs text-sub">
        This tab is wired up and ready — the {tab?.label.toLowerCase() ?? tabId} experience ships in a later stage.
      </div>
    </div>
  );
}

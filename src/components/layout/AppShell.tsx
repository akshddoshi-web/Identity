import { Outlet, useParams } from "react-router-dom";
import { findTab, slugify } from "@/config/tabs";
import { TopNav } from "./TopNav";
import { SubTabNav } from "./SubTabNav";

export function AppShell() {
  const { tabId = "home", subSlug, detailId } = useParams();
  const tab = findTab(tabId) ?? findTab("home")!;
  const activeSub = subSlug ?? slugify(tab.subs[0]);

  return (
    <div className="mx-auto max-w-app px-4 pb-24 pt-7">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-border pb-5">
        <div className="flex items-baseline gap-2.5 text-2xl font-bold tracking-tight">
          <div className="bg-text px-1.5 py-0.5 font-mono text-xs font-bold text-bg">ID</div>
          IDENTITY
          <small className="ml-1 font-mono text-[10px] font-normal uppercase tracking-[2px] text-sub">
            Life OS
          </small>
        </div>
        <div className="flex items-center gap-2 border border-border px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-sub">
          <div className="flex h-5 w-5 items-center justify-center bg-text text-[10px] font-bold text-bg">
            D
          </div>
          DOSHI &nbsp;/&nbsp; DEMO DATA
        </div>
      </header>

      <TopNav activeTab={tab.id} />
      <SubTabNav tabId={tab.id} subs={tab.subs} activeSub={activeSub} />

      <div key={`${tab.id}/${activeSub}/${detailId ?? ""}`}>
        <Outlet />
      </div>

      <div className="mt-9 border-t border-border pt-3.5 text-center text-[11px] leading-relaxed text-sub">
        Prototype UI running entirely in your browser — all data below is sample data, nothing is
        connected to a real bank, brokerage, or league yet.
      </div>
    </div>
  );
}

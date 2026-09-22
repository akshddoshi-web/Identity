import { useNavigate } from "react-router-dom";
import { TABS } from "@/config/tabs";
import { clsx } from "@/lib/clsx";

interface Props {
  activeTab: string;
}

export function TopNav({ activeTab }: Props) {
  const navigate = useNavigate();

  return (
    <nav className="flex overflow-x-auto border border-border">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => navigate(`/${tab.id}`)}
          className={clsx(
            "flex items-center gap-2 whitespace-nowrap border-r border-border px-5 py-3.5 font-mono text-[11.5px] font-medium uppercase tracking-wide last:border-r-0",
            activeTab === tab.id ? "bg-text text-bg" : "bg-transparent text-sub hover:bg-panel3 hover:text-text",
          )}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}

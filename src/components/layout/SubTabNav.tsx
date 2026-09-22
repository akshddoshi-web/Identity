import { useNavigate } from "react-router-dom";
import { slugify } from "@/config/tabs";
import { clsx } from "@/lib/clsx";

interface Props {
  tabId: string;
  subs: string[];
  activeSub: string;
}

export function SubTabNav({ tabId, subs, activeSub }: Props) {
  const navigate = useNavigate();

  if (subs.length === 0) return null;

  return (
    <nav className="mb-5 flex overflow-x-auto border border-t-0 border-border">
      {subs.map((sub) => {
        const slug = slugify(sub);
        return (
          <button
            key={sub}
            onClick={() => navigate(`/${tabId}/${slug}`)}
            className={clsx(
              "whitespace-nowrap border-r border-border px-4 py-2.5 text-xs font-medium last:border-r-0",
              activeSub === slug ? "bg-text text-bg" : "bg-transparent text-sub hover:bg-panel3 hover:text-text",
            )}
          >
            {sub}
          </button>
        );
      })}
    </nav>
  );
}

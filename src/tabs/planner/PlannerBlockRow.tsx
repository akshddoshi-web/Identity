import { useEffect, useRef, useState } from "react";
import type { PlannerBlock, Weekday } from "@/types/planner";
import { usePlannerStore } from "@/store/usePlannerStore";
import { clsx } from "@/lib/clsx";

interface Props {
  day: Weekday;
  block: PlannerBlock;
  color: string;
  variant?: "list" | "grid";
}

/** A single planner block: checkbox + Notion-style click-to-edit text.
 *  Shared by the list view and the time-grid view so inline editing works
 *  identically in both — they're two renderings of the same block data. */
export function PlannerBlockRow({ day, block, color, variant = "list" }: Props) {
  const toggleBlockDone = usePlannerStore((s) => s.toggleBlockDone);
  const editBlockText = usePlannerStore((s) => s.editBlockText);

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(block.text);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  function commit() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== block.text) editBlockText(day, block.id, trimmed);
    else setDraft(block.text);
    setEditing(false);
  }

  function cancel() {
    setDraft(block.text);
    setEditing(false);
  }

  return (
    <label
      className={clsx(
        "flex cursor-pointer items-center gap-1.5 border-l-[3px] py-1.5 pl-2.5 text-[11.5px]",
        block.done && "opacity-50 line-through",
        variant === "grid" && "h-full items-start overflow-hidden bg-panel3",
      )}
      style={{ borderLeftColor: color }}
    >
      <input
        type="checkbox"
        checked={block.done}
        onChange={() => toggleBlockDone(day, block.id)}
        className="mt-0.5 flex-shrink-0 cursor-pointer accent-text"
        onClick={(e) => e.stopPropagation()}
      />
      {editing ? (
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") cancel();
          }}
          onClick={(e) => e.stopPropagation()}
          className="w-full border border-border bg-panel px-1 py-0.5 text-[11.5px] text-text focus:outline-none"
        />
      ) : (
        <span
          onClick={(e) => {
            e.preventDefault();
            setEditing(true);
          }}
          className={clsx(
            "cursor-text hover:underline",
            variant === "grid" && "min-w-0 flex-1 truncate whitespace-nowrap",
          )}
        >
          {block.text}
        </span>
      )}
    </label>
  );
}

"use client";

import { Check, Flag, Trash2, X } from "lucide-react";

import { useAppStore } from "@/components/app-store";
import { Button } from "@/components/ui";
import { PRIORITY_META, type Priority } from "@/lib/domain/types";
import { cn } from "@/lib/utils";

/**
 * Appears only when rows are selected. It floats above the list rather than
 * pushing it down, so the selection stays where the user left it.
 */
export function BulkActionBar() {
  const store = useAppStore();
  const count = store.checkedIds.length;
  if (count === 0) return null;

  return (
    <div
      role="toolbar"
      aria-label={`${count} tasks selected`}
      className={cn(
        "fixed bottom-20 left-1/2 z-40 flex -translate-x-1/2 items-center gap-1.5 md:bottom-6",
        "animate-slide-up rounded-xl bg-surface px-2 py-1.5 shadow-2xl ring-1 ring-border",
      )}
    >
      <span className="px-2 text-sm font-medium tabular-nums">{count} selected</span>

      <Button size="sm" variant="ghost" onClick={store.completeChecked}>
        <Check className="size-4" />
        Complete
      </Button>

      <div className="flex items-center gap-0.5 border-l border-border pl-1.5">
        {([3, 2, 1, 0] as Priority[]).map((value) => (
          <Button
            key={value}
            size="icon-sm"
            variant="ghost"
            aria-label={`Set priority ${PRIORITY_META[value].label}`}
            onClick={() => store.setCheckedPriority(value)}
          >
            <Flag className={cn("size-4 fill-current", PRIORITY_META[value].className)} />
          </Button>
        ))}
      </div>

      <Button size="sm" variant="ghost" className="text-danger" onClick={store.deleteChecked}>
        <Trash2 className="size-4" />
        Delete
      </Button>

      <Button size="icon-sm" variant="ghost" aria-label="Clear selection" onClick={store.clearChecked}>
        <X className="size-4" />
      </Button>
    </div>
  );
}

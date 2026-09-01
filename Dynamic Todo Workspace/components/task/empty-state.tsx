import type { LucideIcon } from "lucide-react";

/**
 * Empty states name the reason the list is empty and, where it makes sense,
 * point at the next action — an empty Today after a full day should read as a
 * win rather than as a broken screen.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border px-6 py-14 text-center">
      <span className="mb-3 grid size-11 place-items-center rounded-full bg-surface-muted text-muted-foreground">
        <Icon className="size-5" />
      </span>
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 max-w-xs text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

import type { TaskLike } from "./types";

export const SORT_MODES = ["manual", "due", "priority", "created", "alpha"] as const;
export type SortMode = (typeof SORT_MODES)[number];

export const SORT_LABELS: Record<SortMode, string> = {
  manual: "Manual order",
  due: "Due date",
  priority: "Priority",
  created: "Date created",
  alpha: "Alphabetical",
};

export function isSortMode(value: unknown): value is SortMode {
  return typeof value === "string" && (SORT_MODES as readonly string[]).includes(value);
}

/** Undated tasks always sink below dated ones, whatever the direction. */
function byDueDate(a: TaskLike, b: TaskLike): number {
  if (!a.dueDate && !b.dueDate) return 0;
  if (!a.dueDate) return 1;
  if (!b.dueDate) return -1;
  return a.dueDate.getTime() - b.dueDate.getTime();
}

const COMPARATORS: Record<SortMode, (a: TaskLike, b: TaskLike) => number> = {
  manual: (a, b) => a.position - b.position,
  due: (a, b) => byDueDate(a, b) || b.priority - a.priority,
  priority: (a, b) => b.priority - a.priority || byDueDate(a, b),
  created: (a, b) => b.createdAt.getTime() - a.createdAt.getTime(),
  alpha: (a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: "base" }),
};

/**
 * Sort a copy of `tasks`. Completed tasks always fall to the bottom so a list
 * does not reshuffle around the item you just ticked off.
 */
export function sortTasks<T extends TaskLike>(tasks: T[], mode: SortMode): T[] {
  const comparator = COMPARATORS[mode];
  return [...tasks].sort(
    (a, b) => Number(a.completed) - Number(b.completed) || comparator(a, b) || a.position - b.position,
  );
}

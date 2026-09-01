import { endOfDay, isSameDay, startOfDay } from "date-fns";

import { matchesSearch } from "./search";
import type { TaskLike } from "./types";

export const VIEWS = ["today", "upcoming", "all", "completed", "trash"] as const;
export type ViewId = (typeof VIEWS)[number];

export function isViewId(value: unknown): value is ViewId {
  return typeof value === "string" && (VIEWS as readonly string[]).includes(value);
}

export interface TaskFilter {
  search?: string;
  projectId?: string | null;
  tagIds?: string[];
  priorities?: number[];
  /** Restrict to overdue tasks only. */
  overdueOnly?: boolean;
}

export const EMPTY_FILTER: TaskFilter = {};

export function isFilterActive(filter: TaskFilter): boolean {
  return Boolean(
    filter.search?.trim() ||
      filter.projectId ||
      filter.tagIds?.length ||
      filter.priorities?.length ||
      filter.overdueOnly,
  );
}

/**
 * Overdue depends on whether the task has a time.
 *
 * An all-day task due today is not overdue at 3pm — you still have the rest of
 * the day. A task due today at 09:00 is overdue at 09:01. Getting this wrong is
 * the single most common way a todo app feels wrong to use.
 */
export function isOverdue(task: Pick<TaskLike, "dueDate" | "hasTime" | "completed">, now: Date): boolean {
  if (task.completed || !task.dueDate) return false;
  return task.hasTime ? task.dueDate < now : startOfDay(task.dueDate) < startOfDay(now);
}

export function isDueToday(task: Pick<TaskLike, "dueDate">, now: Date): boolean {
  return Boolean(task.dueDate && isSameDay(task.dueDate, now));
}

/** Everything that should appear under "Today": due today, plus anything late. */
export function isDueTodayOrOverdue(
  task: Pick<TaskLike, "dueDate" | "hasTime" | "completed">,
  now: Date,
): boolean {
  if (!task.dueDate) return false;
  return isDueToday(task, now) || isOverdue(task, now);
}

/** Days 1..`days` ahead — deliberately excludes today, which has its own view. */
export function isUpcoming(task: Pick<TaskLike, "dueDate">, now: Date, days = 7): boolean {
  if (!task.dueDate) return false;
  const from = endOfDay(now);
  const to = endOfDay(new Date(now.getFullYear(), now.getMonth(), now.getDate() + days));
  return task.dueDate > from && task.dueDate <= to;
}

export function matchesView(task: TaskLike, view: ViewId, now: Date): boolean {
  if (view === "trash") return task.deletedAt !== null;
  if (task.deletedAt) return false;

  switch (view) {
    case "today":
      return !task.completed && isDueTodayOrOverdue(task, now);
    case "upcoming":
      return !task.completed && isUpcoming(task, now);
    case "completed":
      return task.completed;
    case "all":
      return !task.completed;
  }
}

export function matchesFilter(
  task: TaskLike & { tagIds?: string[] },
  filter: TaskFilter,
  now: Date = new Date(),
): boolean {
  if (filter.projectId !== undefined && filter.projectId !== null) {
    if (task.projectId !== filter.projectId) return false;
  }
  if (filter.priorities?.length && !filter.priorities.includes(task.priority)) return false;
  if (filter.tagIds?.length) {
    const ids = task.tagIds ?? [];
    if (!filter.tagIds.some((id) => ids.includes(id))) return false;
  }
  if (filter.overdueOnly && !isOverdue(task, now)) return false;
  if (filter.search?.trim() && !matchesSearch(filter.search, [task.title, task.notes])) return false;
  return true;
}

export interface DayGroup<T> {
  /** Local midnight of the group. Null groups undated tasks. */
  date: Date | null;
  tasks: T[];
}

/** Group tasks by calendar day, oldest first, with undated tasks last. */
export function groupByDay<T extends Pick<TaskLike, "dueDate">>(tasks: T[]): DayGroup<T>[] {
  const groups = new Map<number, DayGroup<T>>();
  const undated: T[] = [];

  for (const task of tasks) {
    if (!task.dueDate) {
      undated.push(task);
      continue;
    }
    const key = startOfDay(task.dueDate).getTime();
    const existing = groups.get(key);
    if (existing) {
      existing.tasks.push(task);
    } else {
      groups.set(key, { date: new Date(key), tasks: [task] });
    }
  }

  const result = Array.from(groups.values()).sort(
    (a, b) => a.date!.getTime() - b.date!.getTime(),
  );
  if (undated.length > 0) result.push({ date: null, tasks: undated });
  return result;
}

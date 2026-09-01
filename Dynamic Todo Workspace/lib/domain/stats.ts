import { differenceInCalendarDays, format, startOfDay, subDays } from "date-fns";

import { isOverdue } from "./filters";
import type { TaskLike } from "./types";

export interface DailyCompletion {
  /** Local midnight of the day. */
  date: Date;
  /** `yyyy-MM-dd`, used as the chart's category key. */
  key: string;
  label: string;
  count: number;
}

export interface TaskStats {
  open: number;
  completed: number;
  overdue: number;
  dueToday: number;
  completedThisWeek: number;
  /** Consecutive days up to today with at least one completion. */
  streak: number;
  /** Share of all non-deleted tasks that are done, 0..1. */
  completionRate: number;
  daily: DailyCompletion[];
}

/**
 * All dashboard numbers in one pass.
 *
 * `tasks` should be every non-deleted task, including completed ones —
 * completion history is what the chart and the streak are made of.
 */
export function computeStats(tasks: TaskLike[], now: Date = new Date(), days = 30): TaskStats {
  const live = tasks.filter((task) => !task.deletedAt);

  const open = live.filter((task) => !task.completed).length;
  const completed = live.length - open;
  const overdue = live.filter((task) => isOverdue(task, now)).length;
  const dueToday = live.filter(
    (task) => !task.completed && task.dueDate !== null && differenceInCalendarDays(task.dueDate, now) === 0,
  ).length;

  const completionsByDay = new Map<string, number>();
  for (const task of live) {
    if (!task.completed || !task.completedAt) continue;
    const key = format(startOfDay(task.completedAt), "yyyy-MM-dd");
    completionsByDay.set(key, (completionsByDay.get(key) ?? 0) + 1);
  }

  const daily: DailyCompletion[] = [];
  for (let offset = days - 1; offset >= 0; offset -= 1) {
    const date = startOfDay(subDays(now, offset));
    const key = format(date, "yyyy-MM-dd");
    daily.push({ date, key, label: format(date, "MMM d"), count: completionsByDay.get(key) ?? 0 });
  }

  const completedThisWeek = daily.slice(-7).reduce((total, day) => total + day.count, 0);

  return {
    open,
    completed,
    overdue,
    dueToday,
    completedThisWeek,
    streak: computeStreak(completionsByDay, now),
    completionRate: live.length === 0 ? 0 : completed / live.length,
    daily,
  };
}

/**
 * Length of the run of consecutive days ending today that have a completion.
 *
 * A day with nothing done today does not break the streak — it is only broken
 * once yesterday is also empty, so the number does not flicker to zero every
 * morning before you have ticked anything off.
 */
export function computeStreak(completionsByDay: Map<string, number>, now: Date): number {
  const hasCompletion = (offset: number) =>
    (completionsByDay.get(format(startOfDay(subDays(now, offset)), "yyyy-MM-dd")) ?? 0) > 0;

  let start = 0;
  if (!hasCompletion(0)) {
    if (!hasCompletion(1)) return 0;
    start = 1;
  }

  let streak = 0;
  for (let offset = start; offset < 3650; offset += 1) {
    if (!hasCompletion(offset)) break;
    streak += 1;
  }
  return streak;
}

export interface ProjectBreakdown {
  projectId: string | null;
  name: string;
  color: string;
  open: number;
  completed: number;
  total: number;
}

export function computeProjectBreakdown(
  tasks: TaskLike[],
  projects: { id: string; name: string; color: string }[],
): ProjectBreakdown[] {
  const byProject = new Map<string, ProjectBreakdown>();
  for (const project of projects) {
    byProject.set(project.id, {
      projectId: project.id,
      name: project.name,
      color: project.color,
      open: 0,
      completed: 0,
      total: 0,
    });
  }

  for (const task of tasks) {
    if (task.deletedAt || !task.projectId) continue;
    const bucket = byProject.get(task.projectId);
    if (!bucket) continue;
    bucket.total += 1;
    if (task.completed) bucket.completed += 1;
    else bucket.open += 1;
  }

  return Array.from(byProject.values())
    .filter((bucket) => bucket.total > 0)
    .sort((a, b) => b.total - a.total);
}

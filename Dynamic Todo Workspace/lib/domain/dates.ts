import {
  differenceInCalendarDays,
  format,
  isSameYear,
  isToday,
  isTomorrow,
  isYesterday,
  startOfDay,
} from "date-fns";

import { isOverdue } from "./filters";
import type { TaskLike } from "./types";

/**
 * How a due date reads on a task row.
 *
 * All-day tasks never show a clock time — showing "12:00 AM" for a task the
 * user simply dated "tomorrow" is the classic tell of a todo app that stores
 * dates carelessly.
 */
export function formatDueDate(
  date: Date,
  hasTime: boolean,
  now: Date = new Date(),
): string {
  const day = formatDueDay(date, now);
  return hasTime ? `${day} ${format(date, "h:mm a")}` : day;
}

export function formatDueDay(date: Date, now: Date = new Date()): string {
  if (isToday(date)) return "Today";
  if (isTomorrow(date)) return "Tomorrow";
  if (isYesterday(date)) return "Yesterday";

  const days = differenceInCalendarDays(date, now);
  // Inside the coming week a weekday name is easier to place than a date.
  if (days > 0 && days < 7) return format(date, "EEEE");
  if (days < 0 && days > -7) return `Last ${format(date, "EEEE")}`;

  return isSameYear(date, now) ? format(date, "MMM d") : format(date, "MMM d, yyyy");
}

/** Heading for a day group, e.g. "Today · Mon, Mar 3". */
export function formatDayHeading(date: Date | null, now: Date = new Date()): string {
  if (!date) return "No date";
  const relative = formatDueDay(date, now);
  const absolute = format(date, "EEE, MMM d");
  return relative === absolute ? absolute : `${relative} · ${absolute}`;
}

export type DueTone = "overdue" | "today" | "soon" | "later" | "none";

/** Which colour a due-date chip should take. */
export function dueTone(
  task: Pick<TaskLike, "dueDate" | "hasTime" | "completed">,
  now: Date = new Date(),
): DueTone {
  if (!task.dueDate) return "none";
  if (isOverdue(task, now)) return "overdue";
  if (isToday(task.dueDate)) return "today";
  return differenceInCalendarDays(task.dueDate, now) <= 3 ? "soon" : "later";
}

/**
 * Combine a calendar day with an optional time, in local time.
 * Without a time the result is local midnight, which is how all-day tasks are
 * stored so that "is it today?" is a plain calendar comparison.
 */
export function combineDateAndTime(day: Date, time: string | null): { dueDate: Date; hasTime: boolean } {
  if (!time) return { dueDate: startOfDay(day), hasTime: false };

  const [hours, minutes] = time.split(":").map(Number);
  const dueDate = startOfDay(day);
  dueDate.setHours(hours ?? 0, minutes ?? 0, 0, 0);
  return { dueDate, hasTime: true };
}

/** The `HH:mm` value for a time input, or empty for an all-day task. */
export function toTimeInputValue(date: Date | null, hasTime: boolean): string {
  return date && hasTime ? format(date, "HH:mm") : "";
}

/** The `yyyy-MM-dd` value for a date input. */
export function toDateInputValue(date: Date | null): string {
  return date ? format(date, "yyyy-MM-dd") : "";
}

/** Parse a `yyyy-MM-dd` input value as a local calendar day, not UTC. */
export function fromDateInputValue(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

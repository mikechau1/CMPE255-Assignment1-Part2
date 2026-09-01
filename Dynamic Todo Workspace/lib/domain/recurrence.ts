import {
  addDays,
  addMonths,
  addWeeks,
  addYears,
  differenceInCalendarWeeks,
  getDay,
  setHours,
  setMilliseconds,
  setMinutes,
  setSeconds,
  startOfWeek,
} from "date-fns";

/**
 * A deliberately small subset of RRULE — enough for the repeats people
 * actually use, and small enough to be exhaustively testable.
 */
export type Frequency = "daily" | "weekly" | "monthly" | "yearly";

export interface RecurrenceRule {
  freq: Frequency;
  /** Repeat every N periods. Always >= 1. */
  interval: number;
  /** Weekly only. 0 = Sunday .. 6 = Saturday. Empty means "same weekday". */
  byDay?: number[];
}

const FREQUENCIES: Frequency[] = ["daily", "weekly", "monthly", "yearly"];

export const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

/** Parse the JSON stored on `Task.recurrence`. Invalid input yields null. */
export function parseRecurrence(raw: string | null | undefined): RecurrenceRule | null {
  if (!raw) return null;

  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  return normalizeRecurrence(value);
}

/** Coerce an unknown value into a valid rule, or null if it cannot be one. */
export function normalizeRecurrence(value: unknown): RecurrenceRule | null {
  if (typeof value !== "object" || value === null) return null;
  const candidate = value as Partial<RecurrenceRule>;

  if (!FREQUENCIES.includes(candidate.freq as Frequency)) return null;

  const interval = Math.trunc(Number(candidate.interval ?? 1));
  const rule: RecurrenceRule = {
    freq: candidate.freq as Frequency,
    interval: Number.isFinite(interval) && interval >= 1 ? interval : 1,
  };

  if (rule.freq === "weekly" && Array.isArray(candidate.byDay)) {
    const days = Array.from(
      new Set(
        candidate.byDay
          .map((day) => Math.trunc(Number(day)))
          .filter((day) => Number.isInteger(day) && day >= 0 && day <= 6),
      ),
    ).sort((a, b) => a - b);
    if (days.length > 0) rule.byDay = days;
  }

  return rule;
}

export function serializeRecurrence(rule: RecurrenceRule | null): string | null {
  return rule ? JSON.stringify(rule) : null;
}

/** Human-readable summary, e.g. "Every 2 weeks on Mon, Wed". */
export function describeRecurrence(rule: RecurrenceRule | null): string {
  if (!rule) return "Does not repeat";

  const { freq, interval } = rule;
  const unit = { daily: "day", weekly: "week", monthly: "month", yearly: "year" }[freq];

  let label: string;
  if (interval === 1) {
    label = { daily: "Daily", weekly: "Weekly", monthly: "Monthly", yearly: "Yearly" }[freq];
  } else if (interval === 2) {
    label = `Every other ${unit}`;
  } else {
    label = `Every ${interval} ${unit}s`;
  }

  if (freq === "weekly" && rule.byDay?.length) {
    label += ` on ${rule.byDay.map((day) => WEEKDAY_LABELS[day]).join(", ")}`;
  }
  return label;
}

/** Copy the clock time of `source` onto `target`'s calendar date. */
function copyTimeOfDay(source: Date, target: Date): Date {
  return setMilliseconds(
    setSeconds(setMinutes(setHours(target, source.getHours()), source.getMinutes()), source.getSeconds()),
    source.getMilliseconds(),
  );
}

/**
 * The first occurrence strictly after `from`.
 *
 * Two behaviours worth knowing:
 *  - Month-end clamps rather than overflows: 31 Jan + 1 month is 28 Feb, not
 *    3 Mar. The day-of-month is not restored afterwards, so a monthly task
 *    started on the 31st settles onto the 28th.
 *  - All arithmetic is on local calendar fields, so a daily task keeps its
 *    wall-clock time across a DST boundary instead of drifting an hour.
 */
export function nextOccurrence(rule: RecurrenceRule, from: Date): Date {
  switch (rule.freq) {
    case "daily":
      return addDays(from, rule.interval);
    case "weekly":
      return nextWeekly(rule, from);
    case "monthly":
      return addMonths(from, rule.interval);
    case "yearly":
      return addYears(from, rule.interval);
  }
}

function nextWeekly(rule: RecurrenceRule, from: Date): Date {
  const days = rule.byDay;
  if (!days || days.length === 0) return addWeeks(from, rule.interval);

  // Any selected weekday still ahead of us inside the current week wins,
  // regardless of the interval — "every 2 weeks on Mon, Wed" completed on the
  // Monday should next land on the Wednesday of that same week.
  for (let offset = 1; offset <= 7; offset += 1) {
    const candidate = addDays(from, offset);
    if (differenceInCalendarWeeks(candidate, from, { weekStartsOn: 0 }) !== 0) break;
    if (days.includes(getDay(candidate))) return candidate;
  }

  // Otherwise jump `interval` weeks and take the first selected weekday.
  const nextWeekStart = addWeeks(startOfWeek(from, { weekStartsOn: 0 }), rule.interval);
  return copyTimeOfDay(from, addDays(nextWeekStart, days[0]!));
}

/**
 * Presets offered in the recurrence picker. `byDay` is filled in at selection
 * time for the "weekdays" preset because it does not depend on the task.
 */
export const RECURRENCE_PRESETS: { id: string; label: string; rule: RecurrenceRule }[] = [
  { id: "daily", label: "Daily", rule: { freq: "daily", interval: 1 } },
  { id: "weekdays", label: "Every weekday", rule: { freq: "weekly", interval: 1, byDay: [1, 2, 3, 4, 5] } },
  { id: "weekly", label: "Weekly", rule: { freq: "weekly", interval: 1 } },
  { id: "biweekly", label: "Every other week", rule: { freq: "weekly", interval: 2 } },
  { id: "monthly", label: "Monthly", rule: { freq: "monthly", interval: 1 } },
  { id: "yearly", label: "Yearly", rule: { freq: "yearly", interval: 1 } },
];

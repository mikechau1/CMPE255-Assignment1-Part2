import {
  addDays,
  addMonths,
  addWeeks,
  addYears,
  getDay,
  setHours,
  setMinutes,
  startOfDay,
} from "date-fns";

import { normalizeRecurrence, type RecurrenceRule } from "./recurrence";
import type { Priority } from "./types";

/**
 * Natural-language quick add.
 *
 * "Pay rent tomorrow 5pm #Home @bills !p1" parses to a due date, a time, a
 * project, a tag, and a priority, with all of those tokens removed from the
 * title. Tokens may appear anywhere in the string.
 *
 * The parser is deliberately conservative: a bare number is never read as a
 * time, so "Buy 5 apples" keeps its 5.
 */
export interface ParsedQuickAdd {
  title: string;
  dueDate: Date | null;
  hasTime: boolean;
  priority: Priority;
  projectName: string | null;
  tagNames: string[];
  recurrence: RecurrenceRule | null;
  /** Character ranges consumed by tokens, for live highlighting in the input. */
  matches: { start: number; end: number; kind: TokenKind }[];
}

export type TokenKind = "project" | "tag" | "priority" | "date" | "time" | "recurrence";

const WEEKDAYS: Record<string, number> = {
  sunday: 0, sun: 0,
  monday: 1, mon: 1,
  tuesday: 2, tue: 2, tues: 2,
  wednesday: 3, wed: 3,
  thursday: 4, thu: 4, thur: 4, thurs: 4,
  friday: 5, fri: 5,
  saturday: 6, sat: 6,
};

const MONTHS: Record<string, number> = {
  jan: 0, january: 0, feb: 1, february: 1, mar: 2, march: 2, apr: 3, april: 3,
  may: 4, jun: 5, june: 5, jul: 6, july: 6, aug: 7, august: 7,
  sep: 8, sept: 8, september: 8, oct: 9, october: 9, nov: 10, november: 10,
  dec: 11, december: 11,
};

const PRIORITY_WORDS: Record<string, Priority> = {
  p1: 3, urgent: 3,
  p2: 2, high: 2,
  p3: 1, medium: 1, med: 1,
  p4: 0, low: 0, none: 0,
};

/** "every day" is daily, not "dayly" — spell the mapping out. */
const UNIT_FREQUENCIES: Record<string, RecurrenceRule["freq"] | undefined> = {
  day: "daily",
  week: "weekly",
  month: "monthly",
  year: "yearly",
};

const UNIT_ADDERS = {
  day: addDays,
  week: addWeeks,
  month: addMonths,
  year: addYears,
} as const;

/** Tracks which characters of the input have already been claimed by a token. */
class Consumed {
  private readonly claimed: boolean[];
  readonly ranges: { start: number; end: number; kind: TokenKind }[] = [];

  constructor(private readonly length: number) {
    this.claimed = new Array(length).fill(false);
  }

  isFree(start: number, end: number): boolean {
    for (let i = start; i < end; i += 1) if (this.claimed[i]) return false;
    return true;
  }

  claim(start: number, end: number, kind: TokenKind): void {
    for (let i = start; i < end; i += 1) this.claimed[i] = true;
    this.ranges.push({ start, end, kind });
  }

  /** The input with every claimed range blanked out. */
  remainder(input: string): string {
    let out = "";
    for (let i = 0; i < this.length; i += 1) out += this.claimed[i] ? " " : input[i];
    return out;
  }
}

/**
 * Run a regex over the input, offering each non-overlapping match to `handler`.
 * The handler returns true to consume the match.
 */
function scan(
  input: string,
  consumed: Consumed,
  pattern: RegExp,
  kind: TokenKind,
  handler: (match: RegExpExecArray) => boolean,
): void {
  const flags = pattern.flags.includes("g") ? pattern.flags : pattern.flags + "g";
  const regex = new RegExp(pattern.source, flags);
  let match: RegExpExecArray | null;
  while ((match = regex.exec(input)) !== null) {
    if (match[0].length === 0) {
      regex.lastIndex += 1;
      continue;
    }
    const start = match.index;
    const end = start + match[0].length;
    if (!consumed.isFree(start, end)) continue;
    if (handler(match)) consumed.claim(start, end, kind);
  }
}

function stripQuotes(value: string): string {
  return value.replace(/^["']|["']$/g, "").trim();
}

/** Next occurrence of `weekday`, strictly after today. */
function nextWeekday(from: Date, weekday: number, forceNextWeek = false): Date {
  const today = startOfDay(from);
  let delta = (weekday - getDay(today) + 7) % 7;
  if (delta === 0) delta = 7;
  if (forceNextWeek && delta < 7) delta += 7;
  return addDays(today, delta);
}

export function parseQuickAdd(input: string, now: Date = new Date()): ParsedQuickAdd {
  const consumed = new Consumed(input.length);

  let dueDate: Date | null = null;
  // Held on an object: TypeScript does not track assignments made inside the
  // scan() callbacks, so a plain `let` would narrow to `never` when read below.
  const clock: { time: { hours: number; minutes: number } | null } = { time: null };
  let priority: Priority = 0;
  let projectName: string | null = null;
  const tagNames: string[] = [];
  let recurrence: RecurrenceRule | null = null;

  // --- Project: #Work or #"Deep Work" -------------------------------------
  scan(input, consumed, /#(?:"([^"]+)"|([\p{L}\p{N}_-]+))/u, "project", (m) => {
    if (projectName !== null) return false;
    const name = stripQuotes(m[1] ?? m[2] ?? "");
    if (!name) return false;
    projectName = name;
    return true;
  });

  // --- Tags: @errands or @"deep focus" ------------------------------------
  scan(input, consumed, /@(?:"([^"]+)"|([\p{L}\p{N}_-]+))/u, "tag", (m) => {
    const name = stripQuotes(m[1] ?? m[2] ?? "");
    if (!name) return false;
    if (!tagNames.some((existing) => existing.toLowerCase() === name.toLowerCase())) {
      tagNames.push(name);
    }
    return true;
  });

  // --- Priority: !p1 / !urgent --------------------------------------------
  scan(input, consumed, /!\s*(p[1-4]|urgent|high|medium|med|low|none)\b/i, "priority", (m) => {
    priority = PRIORITY_WORDS[m[1]!.toLowerCase()] ?? 0;
    return true;
  });

  // --- Recurrence ----------------------------------------------------------
  // "every day", "every 2 weeks", "every other week", "every mon, wed"
  scan(
    input,
    consumed,
    /\bevery\s+(?:(other)\s+)?(?:(\d+)\s+)?(day|week|month|year|weekday|[a-z]{3,9}(?:\s*,\s*[a-z]{3,9})*)s?\b/i,
    "recurrence",
    (m) => {
      if (recurrence) return false;
      const interval = m[1] ? 2 : m[2] ? Number(m[2]) : 1;
      const unit = m[3]!.toLowerCase();

      if (unit === "weekday") {
        recurrence = { freq: "weekly", interval, byDay: [1, 2, 3, 4, 5] };
        return true;
      }
      const freq = UNIT_FREQUENCIES[unit];
      if (freq) {
        recurrence = { freq, interval };
        return true;
      }

      const days = unit
        .split(",")
        .map((part) => WEEKDAYS[part.trim()])
        .filter((day): day is number => day !== undefined);
      if (days.length === 0) return false;

      recurrence = {
        freq: "weekly",
        interval,
        byDay: Array.from(new Set(days)).sort((a, b) => a - b),
      };
      return true;
    },
  );
  scan(input, consumed, /\b(daily|weekly|monthly|yearly|annually)\b/i, "recurrence", (m) => {
    if (recurrence) return false;
    const word = m[1]!.toLowerCase();
    const freq = word === "annually" ? "yearly" : (word as RecurrenceRule["freq"]);
    recurrence = { freq, interval: 1 };
    return true;
  });

  const setDate = (value: Date): boolean => {
    if (dueDate) return false;
    dueDate = startOfDay(value);
    return true;
  };

  // --- Absolute dates ------------------------------------------------------
  // ISO: 2026-03-14
  scan(input, consumed, /\b(\d{4})-(\d{2})-(\d{2})\b/, "date", (m) =>
    setDate(new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))),
  );
  // Numeric: 3/14 or 3/14/2026
  scan(input, consumed, /\b(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?\b/, "date", (m) => {
    const month = Number(m[1]) - 1;
    const day = Number(m[2]);
    if (month < 0 || month > 11 || day < 1 || day > 31) return false;
    let year = m[3] ? Number(m[3]) : now.getFullYear();
    if (year < 100) year += 2000;
    const candidate = new Date(year, month, day);
    // A bare month/day that has already passed means next year.
    if (!m[3] && candidate < startOfDay(now)) candidate.setFullYear(year + 1);
    return setDate(candidate);
  });
  // Month name: "Mar 14"
  scan(input, consumed, /\b([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b/i, "date", (m) => {
    const month = MONTHS[m[1]!.toLowerCase()];
    if (month === undefined) return false;
    const day = Number(m[2]);
    if (day < 1 || day > 31) return false;
    const candidate = new Date(now.getFullYear(), month, day);
    if (candidate < startOfDay(now)) candidate.setFullYear(now.getFullYear() + 1);
    return setDate(candidate);
  });
  // "14 March" / "14th of March"
  scan(input, consumed, /\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3,9})\b/i, "date", (m) => {
    const month = MONTHS[m[2]!.toLowerCase()];
    if (month === undefined) return false;
    const day = Number(m[1]);
    if (day < 1 || day > 31) return false;
    const candidate = new Date(now.getFullYear(), month, day);
    if (candidate < startOfDay(now)) candidate.setFullYear(now.getFullYear() + 1);
    return setDate(candidate);
  });

  // --- Relative dates ------------------------------------------------------
  scan(input, consumed, /\bin\s+(a|an|\d+)\s+(day|week|month|year)s?\b/i, "date", (m) => {
    const amount = /^\d+$/.test(m[1]!) ? Number(m[1]) : 1;
    const unit = m[2]!.toLowerCase() as keyof typeof UNIT_ADDERS;
    return setDate(UNIT_ADDERS[unit](now, amount));
  });
  scan(input, consumed, /\bnext\s+(week|month|year|[a-z]{3,9})\b/i, "date", (m) => {
    const word = m[1]!.toLowerCase();
    if (word === "week") return setDate(addWeeks(now, 1));
    if (word === "month") return setDate(addMonths(now, 1));
    if (word === "year") return setDate(addYears(now, 1));
    const weekday = WEEKDAYS[word];
    if (weekday === undefined) return false;
    return setDate(nextWeekday(now, weekday, true));
  });
  scan(input, consumed, /\b(?:this\s+)?(today|tonight|tomorrow|tmrw?|yesterday)\b/i, "date", (m) => {
    const word = m[1]!.toLowerCase();
    if (word === "tonight") {
      clock.time ??= { hours: 20, minutes: 0 };
      return setDate(now);
    }
    if (word === "today") return setDate(now);
    if (word === "yesterday") return setDate(addDays(now, -1));
    return setDate(addDays(now, 1));
  });
  // Bare or prefixed weekday: "friday", "on friday", "this friday"
  scan(input, consumed, /\b(?:on\s+|this\s+)?([a-z]{3,9})\b/i, "date", (m) => {
    const weekday = WEEKDAYS[m[1]!.toLowerCase()];
    if (weekday === undefined) return false;
    return setDate(nextWeekday(now, weekday));
  });

  // --- Times ---------------------------------------------------------------
  const setTime = (hours: number, minutes: number): boolean => {
    if (clock.time) return false;
    if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) return false;
    clock.time = { hours, minutes };
    return true;
  };

  scan(input, consumed, /\b(noon|midday|midnight)\b/i, "time", (m) =>
    setTime(m[1]!.toLowerCase() === "midnight" ? 0 : 12, 0),
  );
  // 5pm, 5:30 pm — a meridiem or a colon is always required, except after "at".
  scan(input, consumed, /\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/i, "time", (m) => {
    let hours = Number(m[1]);
    if (hours < 1 || hours > 12) return false;
    const meridiem = m[3]!.toLowerCase();
    if (meridiem === "pm" && hours !== 12) hours += 12;
    if (meridiem === "am" && hours === 12) hours = 0;
    return setTime(hours, Number(m[2] ?? 0));
  });
  scan(input, consumed, /\bat\s+(\d{1,2})(?::(\d{2}))?\b/i, "time", (m) => {
    let hours = Number(m[1]);
    const minutes = Number(m[2] ?? 0);
    // "at 5" means the evening; "at 9" means the morning.
    if (m[2] === undefined && hours < 8) hours += 12;
    return setTime(hours, minutes);
  });
  scan(input, consumed, /\b([01]?\d|2[0-3]):([0-5]\d)\b/, "time", (m) =>
    setTime(Number(m[1]), Number(m[2])),
  );

  // --- Assemble ------------------------------------------------------------
  let resolvedDue: Date | null = dueDate;
  let hasTime = false;

  if (clock.time) {
    hasTime = true;
    const base = resolvedDue ?? startOfDay(now);
    let withTime = setMinutes(setHours(base, clock.time.hours), clock.time.minutes);
    // A bare time that has already passed today means tomorrow.
    if (!resolvedDue && withTime <= now) withTime = addDays(withTime, 1);
    resolvedDue = withTime;
  }

  // A repeating task with no date starts today.
  if (!resolvedDue && recurrence) resolvedDue = startOfDay(now);

  return {
    title: cleanTitle(consumed.remainder(input)),
    dueDate: resolvedDue,
    hasTime,
    priority,
    projectName,
    tagNames,
    recurrence: recurrence ? normalizeRecurrence(recurrence) : null,
    matches: consumed.ranges.sort((a, b) => a.start - b.start),
  };
}

/**
 * Tidy what is left after tokens are removed: collapse the gaps they left and
 * drop a dangling preposition, so "Pay rent by tomorrow" becomes "Pay rent"
 * rather than "Pay rent by".
 */
function cleanTitle(remainder: string): string {
  return remainder
    .replace(/\s+/g, " ")
    .trim()
    .replace(/[,\-–—]+$/, "")
    .replace(/\s+\b(on|at|by|due|before|from|until|till|starting)\b\s*$/i, "")
    .replace(/^\b(on|at|by|due|before|from)\b\s+/i, "")
    .trim();
}

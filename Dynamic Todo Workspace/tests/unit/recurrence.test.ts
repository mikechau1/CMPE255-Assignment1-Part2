import { describe, expect, it } from "vitest";

import {
  describeRecurrence,
  nextOccurrence,
  normalizeRecurrence,
  parseRecurrence,
  serializeRecurrence,
  type RecurrenceRule,
} from "@/lib/domain/recurrence";

/** Local-time date helper so these tests do not depend on the machine's zone. */
const at = (y: number, m: number, d: number, h = 9, min = 0) => new Date(y, m - 1, d, h, min);

describe("parseRecurrence", () => {
  it("returns null for empty and malformed input", () => {
    expect(parseRecurrence(null)).toBeNull();
    expect(parseRecurrence("")).toBeNull();
    expect(parseRecurrence("not json")).toBeNull();
    expect(parseRecurrence('{"freq":"hourly"}')).toBeNull();
  });

  it("round-trips a rule", () => {
    const rule: RecurrenceRule = { freq: "weekly", interval: 2, byDay: [1, 3] };
    expect(parseRecurrence(serializeRecurrence(rule))).toEqual(rule);
  });

  it("repairs sloppy values instead of throwing", () => {
    expect(normalizeRecurrence({ freq: "daily", interval: 0 })).toEqual({ freq: "daily", interval: 1 });
    expect(normalizeRecurrence({ freq: "daily", interval: -5 })).toEqual({ freq: "daily", interval: 1 });
    expect(normalizeRecurrence({ freq: "weekly", interval: 1, byDay: [1, 1, 9, 3] })).toEqual({
      freq: "weekly",
      interval: 1,
      byDay: [1, 3],
    });
  });

  it("drops byDay for non-weekly rules", () => {
    expect(normalizeRecurrence({ freq: "monthly", interval: 1, byDay: [1] })).toEqual({
      freq: "monthly",
      interval: 1,
    });
  });
});

describe("nextOccurrence", () => {
  it("advances daily by the interval", () => {
    expect(nextOccurrence({ freq: "daily", interval: 1 }, at(2026, 3, 10))).toEqual(at(2026, 3, 11));
    expect(nextOccurrence({ freq: "daily", interval: 3 }, at(2026, 3, 10))).toEqual(at(2026, 3, 13));
  });

  it("preserves the time of day", () => {
    const next = nextOccurrence({ freq: "daily", interval: 1 }, at(2026, 3, 10, 17, 30));
    expect(next.getHours()).toBe(17);
    expect(next.getMinutes()).toBe(30);
  });

  it("advances weekly with no byDay by whole weeks", () => {
    expect(nextOccurrence({ freq: "weekly", interval: 1 }, at(2026, 3, 10))).toEqual(at(2026, 3, 17));
    expect(nextOccurrence({ freq: "weekly", interval: 2 }, at(2026, 3, 10))).toEqual(at(2026, 3, 24));
  });

  it("takes the next selected weekday inside the same week", () => {
    // 2026-03-09 is a Monday; the rule also selects Wednesday.
    const rule: RecurrenceRule = { freq: "weekly", interval: 1, byDay: [1, 3] };
    expect(nextOccurrence(rule, at(2026, 3, 9))).toEqual(at(2026, 3, 11));
  });

  it("jumps by the interval once the week's selected days are used up", () => {
    // Completed on Wednesday, the last selected day of that week.
    const rule: RecurrenceRule = { freq: "weekly", interval: 2, byDay: [1, 3] };
    const next = nextOccurrence(rule, at(2026, 3, 11));
    // Two weeks on from the Sunday that starts 2026-03-08 is 2026-03-22, and
    // the first selected day in that week is the Monday, 2026-03-23.
    expect(next).toEqual(at(2026, 3, 23));
  });

  it("keeps the time of day when jumping to a new week", () => {
    const rule: RecurrenceRule = { freq: "weekly", interval: 1, byDay: [1] };
    const next = nextOccurrence(rule, at(2026, 3, 9, 14, 45));
    expect(next).toEqual(at(2026, 3, 16, 14, 45));
  });

  it("clamps rather than overflowing at month end", () => {
    // 31 January + 1 month is 28 February, never 3 March.
    expect(nextOccurrence({ freq: "monthly", interval: 1 }, at(2026, 1, 31))).toEqual(at(2026, 2, 28));
  });

  it("clamps 29 February on a non-leap year", () => {
    expect(nextOccurrence({ freq: "yearly", interval: 1 }, at(2024, 2, 29))).toEqual(at(2025, 2, 28));
  });

  it("always moves strictly forward", () => {
    const rules: RecurrenceRule[] = [
      { freq: "daily", interval: 1 },
      { freq: "weekly", interval: 1, byDay: [0, 1, 2, 3, 4, 5, 6] },
      { freq: "monthly", interval: 1 },
      { freq: "yearly", interval: 1 },
    ];
    const from = at(2026, 3, 10);
    for (const rule of rules) {
      expect(nextOccurrence(rule, from).getTime()).toBeGreaterThan(from.getTime());
    }
  });
});

describe("describeRecurrence", () => {
  it("reads naturally", () => {
    expect(describeRecurrence(null)).toBe("Does not repeat");
    expect(describeRecurrence({ freq: "daily", interval: 1 })).toBe("Daily");
    expect(describeRecurrence({ freq: "weekly", interval: 2 })).toBe("Every other week");
    expect(describeRecurrence({ freq: "monthly", interval: 3 })).toBe("Every 3 months");
    expect(describeRecurrence({ freq: "weekly", interval: 1, byDay: [1, 3] })).toBe("Weekly on Mon, Wed");
  });
});

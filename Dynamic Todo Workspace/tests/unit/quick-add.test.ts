import { describe, expect, it } from "vitest";

import { parseQuickAdd } from "@/lib/domain/quick-add";

/** Tuesday 10 March 2026, 09:00 local. */
const NOW = new Date(2026, 2, 10, 9, 0, 0, 0);

const parse = (input: string) => parseQuickAdd(input, NOW);

describe("parseQuickAdd", () => {
  it("leaves a plain title untouched", () => {
    const result = parse("Buy milk");
    expect(result.title).toBe("Buy milk");
    expect(result.dueDate).toBeNull();
    expect(result.hasTime).toBe(false);
    expect(result.priority).toBe(0);
    expect(result.projectName).toBeNull();
    expect(result.tagNames).toEqual([]);
    expect(result.recurrence).toBeNull();
  });

  it("parses the full example end to end", () => {
    const result = parse("Pay rent tomorrow 5pm #Home @bills !p1");
    expect(result.title).toBe("Pay rent");
    expect(result.priority).toBe(3);
    expect(result.projectName).toBe("Home");
    expect(result.tagNames).toEqual(["bills"]);
    expect(result.hasTime).toBe(true);
    expect(result.dueDate).toEqual(new Date(2026, 2, 11, 17, 0, 0, 0));
  });

  it("strips tokens from anywhere in the string", () => {
    const result = parse("#Work Draft @urgent-memo the report tomorrow");
    expect(result.title).toBe("Draft the report");
    expect(result.projectName).toBe("Work");
    expect(result.tagNames).toEqual(["urgent-memo"]);
  });

  it("supports quoted multi-word projects and tags", () => {
    const result = parse('Ship it #"Deep Work" @"code review"');
    expect(result.title).toBe("Ship it");
    expect(result.projectName).toBe("Deep Work");
    expect(result.tagNames).toEqual(["code review"]);
  });

  it("collects several tags but only the first project", () => {
    const result = parse("Plan trip @travel @family #Personal #Other");
    expect(result.tagNames).toEqual(["travel", "family"]);
    expect(result.projectName).toBe("Personal");
    expect(result.title).toBe("Plan trip #Other");
  });

  it("does not mistake numbers in the title for a time", () => {
    const result = parse("Buy 5 apples");
    expect(result.title).toBe("Buy 5 apples");
    expect(result.hasTime).toBe(false);
    expect(result.dueDate).toBeNull();
  });

  it("drops a dangling preposition left behind by a token", () => {
    expect(parse("Pay rent by tomorrow").title).toBe("Pay rent");
    expect(parse("Standup on monday").title).toBe("Standup");
  });

  describe("dates", () => {
    it("understands today, tomorrow and yesterday", () => {
      expect(parse("Ship today").dueDate).toEqual(new Date(2026, 2, 10));
      expect(parse("Ship tomorrow").dueDate).toEqual(new Date(2026, 2, 11));
      expect(parse("Ship yesterday").dueDate).toEqual(new Date(2026, 2, 9));
    });

    it("treats a bare weekday as the next one", () => {
      // NOW is a Tuesday, so "friday" is three days out.
      expect(parse("Gym friday").dueDate).toEqual(new Date(2026, 2, 13));
      // The same weekday means a week from now, never today.
      expect(parse("Gym tuesday").dueDate).toEqual(new Date(2026, 2, 17));
    });

    it("pushes 'next <weekday>' a further week out", () => {
      expect(parse("Review next friday").dueDate).toEqual(new Date(2026, 2, 20));
    });

    it("handles relative offsets", () => {
      expect(parse("Follow up in 3 days").dueDate).toEqual(new Date(2026, 2, 13));
      expect(parse("Follow up in a week").dueDate).toEqual(new Date(2026, 2, 17));
      expect(parse("Renew next month").dueDate).toEqual(new Date(2026, 3, 10));
    });

    it("handles absolute formats", () => {
      expect(parse("Launch 2026-06-01").dueDate).toEqual(new Date(2026, 5, 1));
      expect(parse("Launch 6/1").dueDate).toEqual(new Date(2026, 5, 1));
      expect(parse("Launch Jun 1").dueDate).toEqual(new Date(2026, 5, 1));
      expect(parse("Launch 1 June").dueDate).toEqual(new Date(2026, 5, 1));
    });

    it("rolls a past month/day forward to next year", () => {
      expect(parse("Taxes Jan 5").dueDate).toEqual(new Date(2027, 0, 5));
    });

    it("marks a date without a time as all-day", () => {
      const result = parse("Ship tomorrow");
      expect(result.hasTime).toBe(false);
      expect(result.dueDate).toEqual(new Date(2026, 2, 11, 0, 0, 0, 0));
    });
  });

  describe("times", () => {
    it("parses meridiem and 24-hour forms", () => {
      expect(parse("Call 5pm").dueDate).toEqual(new Date(2026, 2, 10, 17, 0));
      expect(parse("Call 5:30pm").dueDate).toEqual(new Date(2026, 2, 10, 17, 30));
      expect(parse("Call 14:45").dueDate).toEqual(new Date(2026, 2, 10, 14, 45));
      expect(parse("Call noon").dueDate).toEqual(new Date(2026, 2, 10, 12, 0));
    });

    it("reads a bare hour after 'at' as the likelier half of the day", () => {
      expect(parse("Dinner at 7").dueDate).toEqual(new Date(2026, 2, 10, 19, 0));
      expect(parse("Standup at 9:15").dueDate).toEqual(new Date(2026, 2, 10, 9, 15));
    });

    it("rolls a time that already passed today over to tomorrow", () => {
      // NOW is 09:00, so 8am has gone.
      expect(parse("Call 8am").dueDate).toEqual(new Date(2026, 2, 11, 8, 0));
    });

    it("gives 'tonight' an evening time", () => {
      const result = parse("Read tonight");
      expect(result.hasTime).toBe(true);
      expect(result.dueDate).toEqual(new Date(2026, 2, 10, 20, 0));
    });
  });

  describe("priority", () => {
    it("maps p1 to urgent and p4 to none", () => {
      expect(parse("Fix !p1").priority).toBe(3);
      expect(parse("Fix !p2").priority).toBe(2);
      expect(parse("Fix !p3").priority).toBe(1);
      expect(parse("Fix !p4").priority).toBe(0);
    });

    it("accepts words as well as codes", () => {
      expect(parse("Fix !urgent").priority).toBe(3);
      expect(parse("Fix !low").priority).toBe(0);
    });

    it("leaves an unrelated exclamation alone", () => {
      expect(parse("Ship it!").title).toBe("Ship it!");
    });
  });

  describe("recurrence", () => {
    it("parses interval forms", () => {
      expect(parse("Standup every day").recurrence).toEqual({ freq: "daily", interval: 1 });
      expect(parse("Report every 2 weeks").recurrence).toEqual({ freq: "weekly", interval: 2 });
      expect(parse("Report every other week").recurrence).toEqual({ freq: "weekly", interval: 2 });
      expect(parse("Rent monthly").recurrence).toEqual({ freq: "monthly", interval: 1 });
    });

    it("parses selected weekdays", () => {
      expect(parse("Gym every mon, wed").recurrence).toEqual({
        freq: "weekly",
        interval: 1,
        byDay: [1, 3],
      });
      expect(parse("Standup every weekday").recurrence).toEqual({
        freq: "weekly",
        interval: 1,
        byDay: [1, 2, 3, 4, 5],
      });
    });

    it("starts a dateless repeating task today", () => {
      const result = parse("Standup every day");
      expect(result.dueDate).toEqual(new Date(2026, 2, 10));
      expect(result.title).toBe("Standup");
    });
  });

  it("reports the ranges it consumed so the input can highlight them", () => {
    const result = parse("Pay rent tomorrow #Home");
    expect(result.matches.length).toBe(2);
    expect(result.matches.every((m) => m.end > m.start)).toBe(true);
    // Ranges are returned in the order they appear in the input.
    expect(result.matches[0]!.start).toBeLessThan(result.matches[1]!.start);
  });

  it("never returns a title containing a consumed token", () => {
    const result = parse("Email @team about #Q3 planning every friday at 4pm !p2");
    expect(result.title).toBe("Email about planning");
    expect(result.tagNames).toEqual(["team"]);
    expect(result.projectName).toBe("Q3");
    expect(result.priority).toBe(2);
    expect(result.recurrence).toEqual({ freq: "weekly", interval: 1, byDay: [5] });
  });
});

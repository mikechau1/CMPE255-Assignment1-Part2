import { describe, expect, it } from "vitest";

import {
  MIN_GAP,
  POSITION_STEP,
  computePosition,
  needsRebalance,
  positionForDrop,
  rebalance,
} from "@/lib/domain/position";
import { sortTasks } from "@/lib/domain/sort";
import { highlightSegments, matchesSearch, normalize } from "@/lib/domain/search";
import { computeProjectBreakdown, computeStats } from "@/lib/domain/stats";
import type { TaskLike } from "@/lib/domain/types";

function task(overrides: Partial<TaskLike> = {}): TaskLike {
  return {
    id: Math.random().toString(36).slice(2),
    title: "Task",
    notes: null,
    completed: false,
    completedAt: null,
    dueDate: null,
    hasTime: false,
    priority: 0,
    position: 1024,
    recurrence: null,
    deletedAt: null,
    projectId: null,
    parentId: null,
    createdAt: new Date(2026, 2, 1),
    updatedAt: new Date(2026, 2, 1),
    ...overrides,
  };
}

describe("computePosition", () => {
  it("seeds an empty list", () => {
    expect(computePosition(null, null)).toBe(POSITION_STEP);
  });

  it("appends after the last item and prepends before the first", () => {
    expect(computePosition(2048, null)).toBe(2048 + POSITION_STEP);
    expect(computePosition(null, 2048)).toBe(2048 - POSITION_STEP);
  });

  it("takes the midpoint between two neighbours", () => {
    expect(computePosition(1000, 2000)).toBe(1500);
  });

  it("keeps ordering stable over repeated insertions in the same gap", () => {
    let prev = 1000;
    const next = 2000;
    for (let i = 0; i < 20; i += 1) {
      const position = computePosition(prev, next);
      expect(position).toBeGreaterThan(prev);
      expect(position).toBeLessThan(next);
      prev = position;
    }
  });

  it("flags a gap too small to split again", () => {
    expect(needsRebalance(1000, 2000)).toBe(false);
    expect(needsRebalance(1000, 1000 + MIN_GAP / 2)).toBe(true);
    expect(needsRebalance(null, 2000)).toBe(false);
  });

  it("spaces a list out evenly when rebalancing", () => {
    expect(rebalance(["a", "b", "c"])).toEqual([
      { id: "a", position: POSITION_STEP },
      { id: "b", position: POSITION_STEP * 2 },
      { id: "c", position: POSITION_STEP * 3 },
    ]);
  });

  it("computes a drop position from the surrounding list", () => {
    const positions = [100, 200, 300];
    expect(positionForDrop(positions, 0)).toBeLessThan(100);
    expect(positionForDrop(positions, 1)).toBe(150);
    expect(positionForDrop(positions, 3)).toBeGreaterThan(300);
  });
});

describe("sortTasks", () => {
  it("always sinks completed tasks to the bottom", () => {
    const sorted = sortTasks(
      [task({ id: "done", completed: true, position: 1 }), task({ id: "open", position: 2 })],
      "manual",
    );
    expect(sorted.map((t) => t.id)).toEqual(["open", "done"]);
  });

  it("orders by due date with undated tasks last", () => {
    const sorted = sortTasks(
      [
        task({ id: "none" }),
        task({ id: "late", dueDate: new Date(2026, 2, 20) }),
        task({ id: "soon", dueDate: new Date(2026, 2, 11) }),
      ],
      "due",
    );
    expect(sorted.map((t) => t.id)).toEqual(["soon", "late", "none"]);
  });

  it("orders by priority, most urgent first", () => {
    const sorted = sortTasks(
      [task({ id: "low", priority: 0 }), task({ id: "urgent", priority: 3 }), task({ id: "mid", priority: 2 })],
      "priority",
    );
    expect(sorted.map((t) => t.id)).toEqual(["urgent", "mid", "low"]);
  });

  it("does not mutate the input array", () => {
    const input = [task({ id: "b", position: 2 }), task({ id: "a", position: 1 })];
    sortTasks(input, "manual");
    expect(input.map((t) => t.id)).toEqual(["b", "a"]);
  });
});

describe("search", () => {
  it("ignores case and accents", () => {
    expect(normalize("Café")).toBe("cafe");
    expect(matchesSearch("cafe", ["Visit the Café"])).toBe(true);
  });

  it("requires every token to appear", () => {
    expect(matchesSearch("rep tax", ["Report on taxes", null])).toBe(true);
    expect(matchesSearch("zzz tax", ["Report on taxes", null])).toBe(false);
  });

  it("treats an empty query as matching everything", () => {
    expect(matchesSearch("   ", ["anything"])).toBe(true);
  });

  it("returns segments that reassemble into the original text", () => {
    const segments = highlightSegments("Report on taxes", "tax");
    expect(segments.map((s) => s.text).join("")).toBe("Report on taxes");
    expect(segments.filter((s) => s.match).map((s) => s.text)).toEqual(["tax"]);
  });

  it("merges overlapping matches rather than double-wrapping", () => {
    const segments = highlightSegments("taxes", "tax taxes");
    expect(segments.map((s) => s.text).join("")).toBe("taxes");
    expect(segments.filter((s) => s.match)).toHaveLength(1);
  });
});

describe("computeStats", () => {
  const NOW = new Date(2026, 2, 10, 15, 0);

  it("counts open, completed, overdue and due-today", () => {
    const stats = computeStats(
      [
        task({ dueDate: new Date(2026, 2, 10) }),
        task({ dueDate: new Date(2026, 2, 1) }),
        task({ completed: true, completedAt: NOW }),
        task({ deletedAt: NOW }),
      ],
      NOW,
    );
    expect(stats.open).toBe(2);
    expect(stats.completed).toBe(1);
    expect(stats.overdue).toBe(1);
    expect(stats.dueToday).toBe(1);
    expect(stats.completionRate).toBeCloseTo(1 / 3);
  });

  it("returns one chart bucket per day, oldest first", () => {
    const stats = computeStats([], NOW, 30);
    expect(stats.daily).toHaveLength(30);
    expect(stats.daily.at(-1)!.date).toEqual(new Date(2026, 2, 10));
    expect(stats.daily.every((d) => d.count === 0)).toBe(true);
  });

  it("counts a streak of consecutive days", () => {
    const stats = computeStats(
      [
        task({ completed: true, completedAt: new Date(2026, 2, 10, 8) }),
        task({ completed: true, completedAt: new Date(2026, 2, 9, 8) }),
        task({ completed: true, completedAt: new Date(2026, 2, 8, 8) }),
        // Gap on the 7th breaks the run.
        task({ completed: true, completedAt: new Date(2026, 2, 6, 8) }),
      ],
      NOW,
    );
    expect(stats.streak).toBe(3);
  });

  it("does not break the streak just because nothing is done yet today", () => {
    const stats = computeStats(
      [
        task({ completed: true, completedAt: new Date(2026, 2, 9, 8) }),
        task({ completed: true, completedAt: new Date(2026, 2, 8, 8) }),
      ],
      NOW,
    );
    expect(stats.streak).toBe(2);
  });

  it("reports no streak once yesterday is empty too", () => {
    const stats = computeStats([task({ completed: true, completedAt: new Date(2026, 2, 1, 8) })], NOW);
    expect(stats.streak).toBe(0);
  });
});

describe("computeProjectBreakdown", () => {
  it("counts per project and drops empty ones", () => {
    const breakdown = computeProjectBreakdown(
      [
        task({ projectId: "a" }),
        task({ projectId: "a", completed: true }),
        task({ projectId: "b" }),
        task({ projectId: "a", deletedAt: new Date() }),
      ],
      [
        { id: "a", name: "Work", color: "violet" },
        { id: "b", name: "Home", color: "sky" },
        { id: "c", name: "Empty", color: "rose" },
      ],
    );

    expect(breakdown.map((p) => p.name)).toEqual(["Work", "Home"]);
    expect(breakdown[0]).toMatchObject({ open: 1, completed: 1, total: 2 });
  });
});

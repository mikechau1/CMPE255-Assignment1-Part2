import { describe, expect, it } from "vitest";

import {
  groupByDay,
  isOverdue,
  isUpcoming,
  matchesFilter,
  matchesView,
} from "@/lib/domain/filters";
import type { TaskLike } from "@/lib/domain/types";

/** Tuesday 10 March 2026, 15:00 local — deliberately mid-afternoon. */
const NOW = new Date(2026, 2, 10, 15, 0);

function task(overrides: Partial<TaskLike> = {}): TaskLike {
  return {
    id: "t1",
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

describe("isOverdue", () => {
  it("does not call an all-day task due today overdue", () => {
    // The whole day is still available — this is the case most apps get wrong.
    expect(isOverdue(task({ dueDate: new Date(2026, 2, 10), hasTime: false }), NOW)).toBe(false);
  });

  it("calls a timed task overdue once its time has passed", () => {
    expect(isOverdue(task({ dueDate: new Date(2026, 2, 10, 9, 0), hasTime: true }), NOW)).toBe(true);
    expect(isOverdue(task({ dueDate: new Date(2026, 2, 10, 17, 0), hasTime: true }), NOW)).toBe(false);
  });

  it("calls an all-day task from a previous day overdue", () => {
    expect(isOverdue(task({ dueDate: new Date(2026, 2, 9), hasTime: false }), NOW)).toBe(true);
  });

  it("never calls a completed or undated task overdue", () => {
    expect(isOverdue(task({ dueDate: new Date(2026, 2, 1), completed: true }), NOW)).toBe(false);
    expect(isOverdue(task({ dueDate: null }), NOW)).toBe(false);
  });
});

describe("isUpcoming", () => {
  it("covers the next seven days but excludes today", () => {
    expect(isUpcoming(task({ dueDate: new Date(2026, 2, 10, 23, 0) }), NOW)).toBe(false);
    expect(isUpcoming(task({ dueDate: new Date(2026, 2, 11) }), NOW)).toBe(true);
    expect(isUpcoming(task({ dueDate: new Date(2026, 2, 17, 23, 0) }), NOW)).toBe(true);
    expect(isUpcoming(task({ dueDate: new Date(2026, 2, 18) }), NOW)).toBe(false);
  });
});

describe("matchesView", () => {
  it("puts overdue tasks in Today alongside today's tasks", () => {
    expect(matchesView(task({ dueDate: new Date(2026, 2, 10) }), "today", NOW)).toBe(true);
    expect(matchesView(task({ dueDate: new Date(2026, 2, 3) }), "today", NOW)).toBe(true);
    expect(matchesView(task({ dueDate: new Date(2026, 2, 20) }), "today", NOW)).toBe(false);
  });

  it("hides completed tasks from every view but Completed", () => {
    const done = task({ completed: true, dueDate: new Date(2026, 2, 10) });
    expect(matchesView(done, "today", NOW)).toBe(false);
    expect(matchesView(done, "all", NOW)).toBe(false);
    expect(matchesView(done, "completed", NOW)).toBe(true);
  });

  it("hides deleted tasks from every view but Trash", () => {
    const deleted = task({ deletedAt: new Date(2026, 2, 9), dueDate: new Date(2026, 2, 10) });
    expect(matchesView(deleted, "today", NOW)).toBe(false);
    expect(matchesView(deleted, "all", NOW)).toBe(false);
    expect(matchesView(deleted, "completed", NOW)).toBe(false);
    expect(matchesView(deleted, "trash", NOW)).toBe(true);
  });

  it("shows undated open tasks in All only", () => {
    const undated = task();
    expect(matchesView(undated, "all", NOW)).toBe(true);
    expect(matchesView(undated, "today", NOW)).toBe(false);
    expect(matchesView(undated, "upcoming", NOW)).toBe(false);
  });
});

describe("matchesFilter", () => {
  it("matches an empty filter against everything", () => {
    expect(matchesFilter(task(), {}, NOW)).toBe(true);
  });

  it("filters by project, priority and tag", () => {
    const t = { ...task({ projectId: "p1", priority: 2 }), tagIds: ["tag1"] };
    expect(matchesFilter(t, { projectId: "p1" }, NOW)).toBe(true);
    expect(matchesFilter(t, { projectId: "p2" }, NOW)).toBe(false);
    expect(matchesFilter(t, { priorities: [2, 3] }, NOW)).toBe(true);
    expect(matchesFilter(t, { priorities: [0] }, NOW)).toBe(false);
    expect(matchesFilter(t, { tagIds: ["tag1"] }, NOW)).toBe(true);
    expect(matchesFilter(t, { tagIds: ["tag9"] }, NOW)).toBe(false);
  });

  it("searches the title and the notes", () => {
    const t = task({ title: "Write report", notes: "about quarterly taxes" });
    expect(matchesFilter(t, { search: "report" }, NOW)).toBe(true);
    expect(matchesFilter(t, { search: "taxes" }, NOW)).toBe(true);
    expect(matchesFilter(t, { search: "report taxes" }, NOW)).toBe(true);
    expect(matchesFilter(t, { search: "invoice" }, NOW)).toBe(false);
  });

  it("combines conditions with AND", () => {
    const t = task({ projectId: "p1", priority: 3, title: "Ship release" });
    expect(matchesFilter(t, { projectId: "p1", search: "ship" }, NOW)).toBe(true);
    expect(matchesFilter(t, { projectId: "p1", search: "nope" }, NOW)).toBe(false);
  });
});

describe("groupByDay", () => {
  it("orders groups by date and sinks undated tasks to the end", () => {
    const groups = groupByDay([
      task({ id: "c", dueDate: new Date(2026, 2, 12) }),
      task({ id: "a", dueDate: new Date(2026, 2, 11, 9, 0) }),
      task({ id: "n", dueDate: null }),
      task({ id: "b", dueDate: new Date(2026, 2, 11, 18, 0) }),
    ]);

    expect(groups).toHaveLength(3);
    expect(groups[0]!.tasks.map((t) => t.id)).toEqual(["a", "b"]);
    expect(groups[1]!.tasks.map((t) => t.id)).toEqual(["c"]);
    expect(groups[2]!.date).toBeNull();
    expect(groups[2]!.tasks.map((t) => t.id)).toEqual(["n"]);
  });
});

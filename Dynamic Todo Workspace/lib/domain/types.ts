/**
 * Framework-free types shared by the server actions, the UI, and the tests.
 * Nothing in `lib/domain` may import React, Next, or Prisma — that is what
 * makes this layer straightforward to unit test.
 */

export const PRIORITIES = [0, 1, 2, 3] as const;
export type Priority = (typeof PRIORITIES)[number];

export interface PriorityMeta {
  value: Priority;
  label: string;
  /** Quick-add token, Todoist style: p1 is the most urgent. */
  token: string;
  /** Tailwind text colour for the flag icon. */
  className: string;
}

export const PRIORITY_META: Record<Priority, PriorityMeta> = {
  3: { value: 3, label: "Urgent", token: "p1", className: "text-rose-500" },
  2: { value: 2, label: "High", token: "p2", className: "text-amber-500" },
  1: { value: 1, label: "Medium", token: "p3", className: "text-sky-500" },
  0: { value: 0, label: "None", token: "p4", className: "text-slate-400" },
};

export function isPriority(value: unknown): value is Priority {
  return typeof value === "number" && PRIORITIES.includes(value as Priority);
}

export function toPriority(value: unknown): Priority {
  return isPriority(value) ? value : 0;
}

/** The colour palette a project or tag can be tinted with. */
export const ACCENTS = [
  "violet",
  "sky",
  "emerald",
  "amber",
  "rose",
  "cyan",
  "lime",
  "fuchsia",
  "slate",
] as const;
export type Accent = (typeof ACCENTS)[number];

export function isAccent(value: unknown): value is Accent {
  return typeof value === "string" && (ACCENTS as readonly string[]).includes(value);
}

/**
 * The shape the UI and the domain functions operate on. It is a structural
 * subset of the Prisma `Task` row plus its resolved tags, so a Prisma result
 * can be passed straight in.
 */
export interface TaskLike {
  id: string;
  title: string;
  notes: string | null;
  completed: boolean;
  completedAt: Date | null;
  dueDate: Date | null;
  hasTime: boolean;
  priority: number;
  position: number;
  recurrence: string | null;
  deletedAt: Date | null;
  projectId: string | null;
  parentId: string | null;
  createdAt: Date;
  updatedAt: Date;
}

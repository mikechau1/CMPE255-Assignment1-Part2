"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { prisma } from "@/lib/db";
import { POSITION_STEP, computePosition, needsRebalance, rebalance } from "@/lib/domain/position";
import { nextOccurrence, normalizeRecurrence, parseRecurrence, serializeRecurrence } from "@/lib/domain/recurrence";
import { PRIORITIES } from "@/lib/domain/types";

/**
 * Every view is a segment of the same task list, so one revalidation keeps the
 * sidebar counts, the open view, and the stats page consistent after a write.
 */
function revalidateAll() {
  revalidatePath("/", "layout");
}

const recurrenceSchema = z
  .object({
    freq: z.enum(["daily", "weekly", "monthly", "yearly"]),
    interval: z.number().int().min(1).max(365),
    byDay: z.array(z.number().int().min(0).max(6)).optional(),
  })
  .nullable();

const createTaskSchema = z.object({
  title: z.string().trim().min(1, "A task needs a title").max(500),
  notes: z.string().max(10_000).nullish(),
  projectId: z.string().nullish(),
  /** Used by quick add: resolved to a project, creating it if needed. */
  projectName: z.string().trim().max(100).nullish(),
  parentId: z.string().nullish(),
  dueDate: z.coerce.date().nullish(),
  hasTime: z.boolean().optional(),
  priority: z.number().int().refine((v) => (PRIORITIES as readonly number[]).includes(v)).optional(),
  tagNames: z.array(z.string().trim().min(1).max(50)).optional(),
  recurrence: recurrenceSchema.optional(),
});

export type CreateTaskInput = z.input<typeof createTaskSchema>;

export type ActionResult<T = object> = ({ ok: true } & T) | { ok: false; error: string };

/** Position that puts a new task at the end of its list. */
async function nextPosition(where: { projectId?: string | null; parentId?: string | null }) {
  const last = await prisma.task.findFirst({
    where: { ...where, deletedAt: null },
    orderBy: { position: "desc" },
    select: { position: true },
  });
  return (last?.position ?? 0) + POSITION_STEP;
}

async function resolveProjectId(projectId?: string | null, projectName?: string | null) {
  if (projectId) return projectId;

  if (projectName) {
    // SQLite string comparison is case-sensitive, so match in JS instead.
    const projects = await prisma.project.findMany({ select: { id: true, name: true } });
    const existing = projects.find(
      (project) => project.name.toLowerCase() === projectName.toLowerCase(),
    );
    if (existing) return existing.id;

    const last = await prisma.project.findFirst({
      orderBy: { position: "desc" },
      select: { position: true },
    });
    const created = await prisma.project.create({
      data: {
        name: projectName,
        color: "violet",
        position: (last?.position ?? 0) + POSITION_STEP,
      },
    });
    return created.id;
  }

  const inbox = await prisma.project.findFirst({ where: { isInbox: true } });
  return inbox?.id ?? null;
}

/** Find or create each tag by name, case-insensitively. */
async function resolveTagIds(names: string[]): Promise<string[]> {
  const existing = await prisma.tag.findMany({ select: { id: true, name: true } });
  const byName = new Map(existing.map((tag) => [tag.name.toLowerCase(), tag.id]));

  const ids: string[] = [];
  for (const name of names) {
    const found = byName.get(name.toLowerCase());
    if (found) {
      ids.push(found);
      continue;
    }
    const created = await prisma.tag.create({ data: { name, color: "slate" } });
    byName.set(name.toLowerCase(), created.id);
    ids.push(created.id);
  }
  return ids;
}

export async function createTask(input: CreateTaskInput): Promise<ActionResult<{ id: string }>> {
  const parsed = createTaskSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, error: parsed.error.issues[0]?.message ?? "Invalid task" };
  }
  const data = parsed.data;

  const projectId = data.parentId
    ? null
    : await resolveProjectId(data.projectId, data.projectName);
  const tagIds = data.tagNames?.length ? await resolveTagIds(data.tagNames) : [];

  const task = await prisma.task.create({
    data: {
      title: data.title,
      notes: data.notes ?? null,
      projectId: data.parentId ? undefined : projectId,
      parentId: data.parentId ?? null,
      dueDate: data.dueDate ?? null,
      hasTime: data.hasTime ?? false,
      priority: data.priority ?? 0,
      recurrence: serializeRecurrence(data.recurrence ? normalizeRecurrence(data.recurrence) : null),
      position: await nextPosition(
        data.parentId ? { parentId: data.parentId } : { projectId, parentId: null },
      ),
      tags: tagIds.length ? { create: tagIds.map((tagId) => ({ tagId })) } : undefined,
    },
    select: { id: true },
  });

  revalidateAll();
  return { ok: true, id: task.id };
}

const updateTaskSchema = z.object({
  id: z.string().min(1),
  title: z.string().trim().min(1).max(500).optional(),
  notes: z.string().max(10_000).nullable().optional(),
  dueDate: z.coerce.date().nullable().optional(),
  hasTime: z.boolean().optional(),
  priority: z.number().int().refine((v) => (PRIORITIES as readonly number[]).includes(v)).optional(),
  projectId: z.string().nullable().optional(),
  recurrence: recurrenceSchema.optional(),
  tagIds: z.array(z.string()).optional(),
});

export type UpdateTaskInput = z.input<typeof updateTaskSchema>;

export async function updateTask(input: UpdateTaskInput): Promise<ActionResult> {
  const parsed = updateTaskSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, error: parsed.error.issues[0]?.message ?? "Invalid change" };
  }
  const { id, tagIds, recurrence, ...fields } = parsed.data;

  const existing = await prisma.task.findUnique({ where: { id }, select: { id: true } });
  if (!existing) return { ok: false, error: "That task no longer exists" };

  await prisma.task.update({
    where: { id },
    data: {
      ...fields,
      ...(recurrence !== undefined
        ? { recurrence: serializeRecurrence(recurrence ? normalizeRecurrence(recurrence) : null) }
        : {}),
    },
  });

  if (tagIds) {
    // Replace the whole set — simpler than diffing, and the sets are tiny.
    await prisma.taskTag.deleteMany({ where: { taskId: id } });
    if (tagIds.length) {
      await prisma.taskTag.createMany({ data: tagIds.map((tagId) => ({ taskId: id, tagId })) });
    }
  }

  revalidateAll();
  return { ok: true };
}

/**
 * Tick a task off, or un-tick it.
 *
 * Completing a repeating task does not just mark it done: it also schedules the
 * next occurrence. The new task's id comes back so undo can remove it again.
 */
export async function toggleTask(
  id: string,
  completed: boolean,
): Promise<ActionResult<{ spawnedTaskId: string | null }>> {
  const task = await prisma.task.findUnique({
    where: { id },
    include: { tags: true },
  });
  if (!task) return { ok: false, error: "That task no longer exists" };

  await prisma.task.update({
    where: { id },
    data: { completed, completedAt: completed ? new Date() : null },
  });

  let spawnedTaskId: string | null = null;
  const rule = parseRecurrence(task.recurrence);

  if (completed && rule) {
    const from = task.dueDate ?? new Date();
    const nextDue = nextOccurrence(rule, from);

    const spawned = await prisma.task.create({
      data: {
        title: task.title,
        notes: task.notes,
        projectId: task.projectId,
        parentId: task.parentId,
        dueDate: nextDue,
        hasTime: task.hasTime,
        priority: task.priority,
        recurrence: task.recurrence,
        position: task.position,
        tags: { create: task.tags.map((link) => ({ tagId: link.tagId })) },
      },
      select: { id: true },
    });
    spawnedTaskId = spawned.id;

    // The completed instance keeps the history but stops repeating, so a task
    // never spawns a second copy if it is un-ticked and ticked again.
    await prisma.task.update({ where: { id }, data: { recurrence: null } });
  }

  revalidateAll();
  return { ok: true, spawnedTaskId };
}

/** Reverse of `toggleTask`, including the occurrence it may have created. */
export async function undoToggle(
  id: string,
  spawnedTaskId: string | null,
  recurrence: string | null,
): Promise<ActionResult> {
  if (spawnedTaskId) {
    await prisma.task.delete({ where: { id: spawnedTaskId } }).catch(() => undefined);
  }
  await prisma.task.update({
    where: { id },
    data: { completed: false, completedAt: null, recurrence },
  });

  revalidateAll();
  return { ok: true };
}

/** Soft delete, so the toast's Undo has something to restore. */
export async function deleteTask(id: string): Promise<ActionResult> {
  const now = new Date();
  await prisma.task.updateMany({ where: { id }, data: { deletedAt: now } });
  await prisma.task.updateMany({ where: { parentId: id }, data: { deletedAt: now } });

  revalidateAll();
  return { ok: true };
}

export async function restoreTask(id: string): Promise<ActionResult> {
  await prisma.task.updateMany({ where: { id }, data: { deletedAt: null } });
  await prisma.task.updateMany({ where: { parentId: id }, data: { deletedAt: null } });

  revalidateAll();
  return { ok: true };
}

/** Permanent delete. Subtasks go with it through the cascade. */
export async function purgeTask(id: string): Promise<ActionResult> {
  await prisma.task.delete({ where: { id } }).catch(() => undefined);
  revalidateAll();
  return { ok: true };
}

export async function emptyTrash(): Promise<ActionResult> {
  await prisma.task.deleteMany({ where: { deletedAt: { not: null } } });
  revalidateAll();
  return { ok: true };
}

const reorderSchema = z.object({
  id: z.string().min(1),
  /** The list's task ids in their new order, the dragged task included. */
  orderedIds: z.array(z.string().min(1)).min(1),
});

/**
 * Persist a drag-and-drop reorder.
 *
 * Only the moved row is written: its new position is the midpoint of its new
 * neighbours. If those neighbours have drifted too close to split, the list is
 * renumbered first.
 */
export async function reorderTask(input: z.input<typeof reorderSchema>): Promise<ActionResult> {
  const parsed = reorderSchema.safeParse(input);
  if (!parsed.success) return { ok: false, error: "Invalid reorder" };
  const { id, orderedIds } = parsed.data;

  const toIndex = orderedIds.indexOf(id);
  if (toIndex === -1) return { ok: false, error: "Invalid reorder" };

  const rows = await prisma.task.findMany({
    where: { id: { in: orderedIds } },
    select: { id: true, position: true },
  });
  const positionById = new Map(rows.map((row) => [row.id, row.position]));

  const neighbours = orderedIds.filter((taskId) => taskId !== id);
  const prevId = toIndex > 0 ? neighbours[toIndex - 1] : undefined;
  const nextId = toIndex < neighbours.length ? neighbours[toIndex] : undefined;

  const prev = prevId ? positionById.get(prevId) ?? null : null;
  const next = nextId ? positionById.get(nextId) ?? null : null;

  if (needsRebalance(prev, next)) {
    for (const { id: taskId, position } of rebalance(orderedIds)) {
      await prisma.task.update({ where: { id: taskId }, data: { position } });
    }
  } else {
    await prisma.task.update({ where: { id }, data: { position: computePosition(prev, next) } });
  }

  revalidateAll();
  return { ok: true };
}

/** Bulk operations from the multi-select toolbar. */
export async function bulkComplete(ids: string[]): Promise<ActionResult> {
  await prisma.task.updateMany({
    where: { id: { in: ids } },
    data: { completed: true, completedAt: new Date() },
  });
  revalidateAll();
  return { ok: true };
}

export async function bulkDelete(ids: string[]): Promise<ActionResult> {
  const now = new Date();
  await prisma.task.updateMany({ where: { id: { in: ids } }, data: { deletedAt: now } });
  await prisma.task.updateMany({ where: { parentId: { in: ids } }, data: { deletedAt: now } });
  revalidateAll();
  return { ok: true };
}

export async function bulkRestore(ids: string[]): Promise<ActionResult> {
  await prisma.task.updateMany({ where: { id: { in: ids } }, data: { deletedAt: null } });
  revalidateAll();
  return { ok: true };
}

export async function bulkSetPriority(ids: string[], priority: number): Promise<ActionResult> {
  if (!(PRIORITIES as readonly number[]).includes(priority)) {
    return { ok: false, error: "Unknown priority" };
  }
  await prisma.task.updateMany({ where: { id: { in: ids } }, data: { priority } });
  revalidateAll();
  return { ok: true };
}

export async function bulkMoveToProject(ids: string[], projectId: string): Promise<ActionResult> {
  await prisma.task.updateMany({ where: { id: { in: ids } }, data: { projectId } });
  revalidateAll();
  return { ok: true };
}

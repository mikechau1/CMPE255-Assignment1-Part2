"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { prisma } from "@/lib/db";
import { POSITION_STEP, computePosition } from "@/lib/domain/position";
import { ACCENTS } from "@/lib/domain/types";

import type { ActionResult } from "./tasks";

function revalidateAll() {
  revalidatePath("/", "layout");
}

const accentSchema = z.enum(ACCENTS);

const projectSchema = z.object({
  name: z.string().trim().min(1, "A project needs a name").max(100),
  color: accentSchema.optional(),
  emoji: z.string().trim().max(8).nullish(),
});

export async function createProject(
  input: z.input<typeof projectSchema>,
): Promise<ActionResult<{ id: string }>> {
  const parsed = projectSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, error: parsed.error.issues[0]?.message ?? "Invalid project" };
  }

  const last = await prisma.project.findFirst({
    orderBy: { position: "desc" },
    select: { position: true },
  });

  const project = await prisma.project.create({
    data: {
      name: parsed.data.name,
      color: parsed.data.color ?? "violet",
      emoji: parsed.data.emoji ?? null,
      position: (last?.position ?? 0) + POSITION_STEP,
    },
    select: { id: true },
  });

  revalidateAll();
  return { ok: true, id: project.id };
}

export async function updateProject(
  id: string,
  input: Partial<z.input<typeof projectSchema>>,
): Promise<ActionResult> {
  const parsed = projectSchema.partial().safeParse(input);
  if (!parsed.success) {
    return { ok: false, error: parsed.error.issues[0]?.message ?? "Invalid project" };
  }

  await prisma.project.update({
    where: { id },
    data: {
      ...(parsed.data.name !== undefined ? { name: parsed.data.name } : {}),
      ...(parsed.data.color !== undefined ? { color: parsed.data.color } : {}),
      ...(parsed.data.emoji !== undefined ? { emoji: parsed.data.emoji ?? null } : {}),
    },
  });

  revalidateAll();
  return { ok: true };
}

/**
 * Delete a project and move its tasks to the Inbox.
 *
 * Reassigning rather than cascading means deleting a list never silently
 * destroys work — the schema's SetNull would leave tasks homeless instead.
 */
export async function deleteProject(id: string): Promise<ActionResult> {
  const project = await prisma.project.findUnique({ where: { id } });
  if (!project) return { ok: false, error: "That project no longer exists" };
  if (project.isInbox) return { ok: false, error: "The Inbox cannot be deleted" };

  const inbox = await prisma.project.findFirst({ where: { isInbox: true } });
  await prisma.task.updateMany({
    where: { projectId: id },
    data: { projectId: inbox?.id ?? null },
  });
  await prisma.project.delete({ where: { id } });

  revalidateAll();
  return { ok: true };
}

export async function reorderProject(id: string, orderedIds: string[]): Promise<ActionResult> {
  const toIndex = orderedIds.indexOf(id);
  if (toIndex === -1) return { ok: false, error: "Invalid reorder" };

  const rows = await prisma.project.findMany({
    where: { id: { in: orderedIds } },
    select: { id: true, position: true },
  });
  const positionById = new Map(rows.map((row) => [row.id, row.position]));

  const neighbours = orderedIds.filter((projectId) => projectId !== id);
  const prevId = toIndex > 0 ? neighbours[toIndex - 1] : undefined;
  const nextId = toIndex < neighbours.length ? neighbours[toIndex] : undefined;

  await prisma.project.update({
    where: { id },
    data: {
      position: computePosition(
        prevId ? positionById.get(prevId) ?? null : null,
        nextId ? positionById.get(nextId) ?? null : null,
      ),
    },
  });

  revalidateAll();
  return { ok: true };
}

const tagSchema = z.object({
  name: z.string().trim().min(1, "A tag needs a name").max(50),
  color: accentSchema.optional(),
});

export async function createTag(
  input: z.input<typeof tagSchema>,
): Promise<ActionResult<{ id: string }>> {
  const parsed = tagSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, error: parsed.error.issues[0]?.message ?? "Invalid tag" };
  }

  const existing = await prisma.tag.findMany({ select: { id: true, name: true } });
  const match = existing.find(
    (tag) => tag.name.toLowerCase() === parsed.data.name.toLowerCase(),
  );
  if (match) return { ok: true, id: match.id };

  const tag = await prisma.tag.create({
    data: { name: parsed.data.name, color: parsed.data.color ?? "slate" },
    select: { id: true },
  });

  revalidateAll();
  return { ok: true, id: tag.id };
}

export async function deleteTag(id: string): Promise<ActionResult> {
  await prisma.tag.delete({ where: { id } }).catch(() => undefined);
  revalidateAll();
  return { ok: true };
}

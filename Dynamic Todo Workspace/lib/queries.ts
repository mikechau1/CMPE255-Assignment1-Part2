import "server-only";

import { prisma } from "./db";
import type { TaskLike } from "./domain/types";

/**
 * The task shape everything above the database speaks.
 *
 * Prisma's nested relation rows are flattened here so components never have to
 * reach through `task.tags[0].tag.name`, and so the object stays cheap to send
 * across the server/client boundary.
 */
export interface TaskDTO extends TaskLike {
  tagIds: string[];
  tags: TagDTO[];
  subtaskTotal: number;
  subtaskDone: number;
}

export interface TagDTO {
  id: string;
  name: string;
  color: string;
}

export interface ProjectDTO {
  id: string;
  name: string;
  color: string;
  emoji: string | null;
  isInbox: boolean;
  position: number;
  openCount: number;
}

const taskInclude = {
  tags: { include: { tag: true } },
  children: { select: { id: true, completed: true, deletedAt: true } },
} as const;

type TaskRow = {
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
  tags: { tag: { id: string; name: string; color: string } }[];
  children: { id: string; completed: boolean; deletedAt: Date | null }[];
};

function toDTO(row: TaskRow): TaskDTO {
  const children = row.children.filter((child) => child.deletedAt === null);
  return {
    id: row.id,
    title: row.title,
    notes: row.notes,
    completed: row.completed,
    completedAt: row.completedAt,
    dueDate: row.dueDate,
    hasTime: row.hasTime,
    priority: row.priority,
    position: row.position,
    recurrence: row.recurrence,
    deletedAt: row.deletedAt,
    projectId: row.projectId,
    parentId: row.parentId,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
    tagIds: row.tags.map((link) => link.tag.id),
    tags: row.tags.map((link) => link.tag),
    subtaskTotal: children.length,
    subtaskDone: children.filter((child) => child.completed).length,
  };
}

/**
 * Every live top-level task, completed ones included.
 *
 * View and filter selection happens in `lib/domain/filters.ts` rather than in
 * SQL: the date rules are the fiddly part, and running them in one tested place
 * beats keeping a parallel set of Prisma `where` clauses correct. A personal
 * todo list is small enough that this costs nothing.
 */
export async function getTasks(): Promise<TaskDTO[]> {
  const rows = await prisma.task.findMany({
    where: { deletedAt: null, parentId: null },
    include: taskInclude,
    orderBy: { position: "asc" },
  });
  return rows.map(toDTO);
}

export async function getDeletedTasks(): Promise<TaskDTO[]> {
  const rows = await prisma.task.findMany({
    where: { deletedAt: { not: null }, parentId: null },
    include: taskInclude,
    orderBy: { deletedAt: "desc" },
  });
  return rows.map(toDTO);
}

export async function getSubtasks(parentId: string): Promise<TaskDTO[]> {
  const rows = await prisma.task.findMany({
    where: { parentId, deletedAt: null },
    include: taskInclude,
    orderBy: { position: "asc" },
  });
  return rows.map(toDTO);
}

export async function getTask(id: string): Promise<TaskDTO | null> {
  const row = await prisma.task.findUnique({ where: { id }, include: taskInclude });
  return row ? toDTO(row) : null;
}

export async function getProjects(): Promise<ProjectDTO[]> {
  const rows = await prisma.project.findMany({
    orderBy: { position: "asc" },
    include: {
      _count: {
        select: { tasks: { where: { completed: false, deletedAt: null, parentId: null } } },
      },
    },
  });

  return rows.map((row) => ({
    id: row.id,
    name: row.name,
    color: row.color,
    emoji: row.emoji,
    isInbox: row.isInbox,
    position: row.position,
    openCount: row._count.tasks,
  }));
}

export async function getProject(id: string) {
  return prisma.project.findUnique({ where: { id } });
}

export async function getTags(): Promise<TagDTO[]> {
  return prisma.tag.findMany({
    orderBy: { name: "asc" },
    select: { id: true, name: true, color: true },
  });
}

/** Tasks for the stats page — subtasks included, since finishing one is work done. */
export async function getAllTasksForStats(): Promise<TaskLike[]> {
  return prisma.task.findMany({
    where: { deletedAt: null },
    orderBy: { createdAt: "asc" },
  });
}

export async function getTrashCount(): Promise<number> {
  return prisma.task.count({ where: { deletedAt: { not: null }, parentId: null } });
}

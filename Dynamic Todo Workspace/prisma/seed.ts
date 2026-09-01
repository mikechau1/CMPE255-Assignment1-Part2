import path from "node:path";

import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3";
import { PrismaClient } from "@prisma/client";
import { addDays, setHours, startOfDay, subDays } from "date-fns";

import { resolveDatabaseUrl } from "../lib/database-url";
import { POSITION_STEP } from "../lib/domain/position";
import { serializeRecurrence } from "../lib/domain/recurrence";

const projectRoot = path.resolve(import.meta.dirname, "..");
try {
  process.loadEnvFile(path.join(projectRoot, ".env"));
} catch {
  // Fall back to the default path inside resolveDatabaseUrl.
}

const prisma = new PrismaClient({
  adapter: new PrismaBetterSqlite3({ url: resolveDatabaseUrl(projectRoot) }),
});

const NOW = new Date();
const TODAY = startOfDay(NOW);

/** Local time on a day offset from today. */
const at = (dayOffset: number, hours?: number) => {
  const day = addDays(TODAY, dayOffset);
  return hours === undefined ? day : setHours(day, hours);
};

interface SeedTask {
  title: string;
  notes?: string;
  project: "inbox" | "work" | "personal" | "learning";
  dueDate?: Date;
  hasTime?: boolean;
  priority?: number;
  tags?: string[];
  recurrence?: { freq: "daily" | "weekly" | "monthly" | "yearly"; interval: number; byDay?: number[] };
  /** Days ago it was completed. Omit for an open task. */
  completedDaysAgo?: number;
  subtasks?: { title: string; done?: boolean }[];
}

/**
 * Deliberately spread across every view: something overdue, something due
 * today, a full upcoming week, undated tasks, and three weeks of completion
 * history so the stats page and the streak counter have real shape.
 */
const SEED_TASKS: SeedTask[] = [
  // --- Overdue -------------------------------------------------------------
  {
    title: "Renew parking permit",
    notes: "The online portal needs the license plate and the student ID.",
    project: "personal",
    dueDate: at(-3),
    priority: 3,
    tags: ["admin"],
  },
  {
    title: "Send updated invoice to accounting",
    project: "work",
    dueDate: at(-1, 16),
    hasTime: true,
    priority: 2,
    tags: ["admin"],
  },

  // --- Due today -----------------------------------------------------------
  {
    title: "Team standup",
    project: "work",
    dueDate: at(0, 9),
    hasTime: true,
    priority: 1,
    recurrence: { freq: "weekly", interval: 1, byDay: [1, 2, 3, 4, 5] },
    tags: ["quick"],
  },
  {
    title: "Finish CMPE 255 assignment write-up",
    notes: "Cover the data model, the optimistic update path, and the test strategy.",
    project: "learning",
    dueDate: at(0),
    priority: 3,
    tags: ["focus"],
    subtasks: [
      { title: "Outline the architecture section", done: true },
      { title: "Add screenshots of each view" },
      { title: "Proofread and export to PDF" },
    ],
  },
  {
    title: "Review pull request #212",
    project: "work",
    dueDate: at(0, 14),
    hasTime: true,
    priority: 2,
    tags: ["focus"],
  },
  { title: "Water the plants", project: "personal", dueDate: at(0), tags: ["quick"] },

  // --- Upcoming ------------------------------------------------------------
  {
    title: "Prep slides for the design review",
    project: "work",
    dueDate: at(1, 10),
    hasTime: true,
    priority: 2,
    tags: ["focus"],
    subtasks: [{ title: "Pull the latest metrics" }, { title: "Rehearse the walkthrough" }],
  },
  { title: "Groceries for the week", project: "personal", dueDate: at(1), tags: ["errand"] },
  {
    title: "Read chapter 4 of the clustering text",
    project: "learning",
    dueDate: at(2),
    priority: 1,
    tags: ["reading"],
  },
  { title: "Dentist appointment", project: "personal", dueDate: at(3, 11), hasTime: true, priority: 2 },
  { title: "Refactor the export pipeline", project: "work", dueDate: at(4), priority: 1, tags: ["focus"] },
  { title: "Call the landlord about the radiator", project: "personal", dueDate: at(5), tags: ["errand"] },
  {
    title: "Weekly review",
    project: "personal",
    dueDate: at(6, 17),
    hasTime: true,
    recurrence: { freq: "weekly", interval: 1 },
    tags: ["admin"],
  },
  {
    title: "Pay rent",
    project: "personal",
    dueDate: at(12, 9),
    hasTime: true,
    priority: 3,
    recurrence: { freq: "monthly", interval: 1 },
    tags: ["admin"],
  },
  { title: "Book flights for the conference", project: "work", dueDate: at(16), priority: 2 },

  // --- Undated -------------------------------------------------------------
  { title: "Try the new vector database tutorial", project: "learning", tags: ["reading"] },
  { title: "Sort out the photo backlog", project: "personal", priority: 0 },
  { title: "Ideas for the capstone project", project: "inbox", notes: "Anomaly detection on transit data?" },
  { title: "Reply to the alumni newsletter", project: "inbox", tags: ["quick"] },

  // --- Completion history --------------------------------------------------
  { title: "Submit midterm reflection", project: "learning", completedDaysAgo: 0, priority: 2 },
  { title: "Clear the inbox", project: "work", completedDaysAgo: 0, tags: ["quick"] },
  { title: "Fix the flaky reorder test", project: "work", completedDaysAgo: 1, priority: 2 },
  { title: "Meal prep", project: "personal", completedDaysAgo: 1, tags: ["errand"] },
  { title: "Draft the migration plan", project: "work", completedDaysAgo: 2, priority: 3 },
  { title: "Read chapter 3", project: "learning", completedDaysAgo: 2, tags: ["reading"] },
  { title: "Return the library books", project: "personal", completedDaysAgo: 3, tags: ["errand"] },
  { title: "Update the dependency lockfile", project: "work", completedDaysAgo: 5 },
  { title: "Write unit tests for the parser", project: "work", completedDaysAgo: 6, priority: 2 },
  { title: "Set up the new laptop", project: "personal", completedDaysAgo: 8 },
  { title: "Finish week 2 problem set", project: "learning", completedDaysAgo: 9, priority: 2 },
  { title: "Archive last term's notes", project: "learning", completedDaysAgo: 12 },
  { title: "Cancel the unused subscription", project: "personal", completedDaysAgo: 14, tags: ["admin"] },
  { title: "Onboard the new teammate", project: "work", completedDaysAgo: 17, priority: 1 },
];

const TAGS: { name: string; color: string }[] = [
  { name: "focus", color: "violet" },
  { name: "quick", color: "emerald" },
  { name: "errand", color: "amber" },
  { name: "reading", color: "sky" },
  { name: "admin", color: "slate" },
];

async function main() {
  console.log("Seeding database…");

  // Order matters: TaskTag and subtasks cascade, but be explicit anyway.
  await prisma.taskTag.deleteMany();
  await prisma.task.deleteMany();
  await prisma.tag.deleteMany();
  await prisma.project.deleteMany();

  const projects = {
    inbox: await prisma.project.create({
      data: { name: "Inbox", color: "slate", emoji: "📥", isInbox: true, position: POSITION_STEP },
    }),
    work: await prisma.project.create({
      data: { name: "Work", color: "violet", emoji: "💼", position: POSITION_STEP * 2 },
    }),
    personal: await prisma.project.create({
      data: { name: "Personal", color: "emerald", emoji: "🏡", position: POSITION_STEP * 3 },
    }),
    learning: await prisma.project.create({
      data: { name: "Learning", color: "sky", emoji: "📚", position: POSITION_STEP * 4 },
    }),
  };

  const tags = new Map<string, string>();
  for (const tag of TAGS) {
    const created = await prisma.tag.create({ data: tag });
    tags.set(tag.name, created.id);
  }

  let position = 0;
  for (const seed of SEED_TASKS) {
    position += POSITION_STEP;

    const completed = seed.completedDaysAgo !== undefined;
    // Completions land mid-morning so they group cleanly by local day.
    const completedAt = completed ? setHours(subDays(TODAY, seed.completedDaysAgo!), 10) : null;

    const task = await prisma.task.create({
      data: {
        title: seed.title,
        notes: seed.notes ?? null,
        projectId: projects[seed.project].id,
        dueDate: seed.dueDate ?? null,
        hasTime: seed.hasTime ?? false,
        priority: seed.priority ?? 0,
        position,
        recurrence: seed.recurrence ? serializeRecurrence(seed.recurrence) : null,
        completed,
        completedAt,
        // Backdate creation so "sort by created" and the charts look natural.
        createdAt: completedAt ? subDays(completedAt, 2) : subDays(NOW, 3),
        tags: seed.tags
          ? {
              create: seed.tags
                .map((name) => tags.get(name))
                .filter((id): id is string => Boolean(id))
                .map((tagId) => ({ tagId })),
            }
          : undefined,
      },
    });

    if (seed.subtasks) {
      let childPosition = 0;
      for (const subtask of seed.subtasks) {
        childPosition += POSITION_STEP;
        await prisma.task.create({
          data: {
            title: subtask.title,
            parentId: task.id,
            projectId: task.projectId,
            position: childPosition,
            completed: Boolean(subtask.done),
            completedAt: subtask.done ? subDays(NOW, 1) : null,
          },
        });
      }
    }
  }

  const [projectCount, taskCount, tagCount] = await Promise.all([
    prisma.project.count(),
    prisma.task.count(),
    prisma.tag.count(),
  ]);
  console.log(`Seeded ${projectCount} projects, ${taskCount} tasks, ${tagCount} tags.`);
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });

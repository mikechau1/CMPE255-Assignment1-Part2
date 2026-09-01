"use client";

import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import {
  bulkComplete,
  bulkDelete,
  bulkSetPriority,
  createTask,
  deleteTask,
  reorderTask,
  restoreTask,
  toggleTask,
  undoToggle,
  updateTask,
  type CreateTaskInput,
} from "@/app/actions/tasks";
import { computePosition } from "@/lib/domain/position";
import { EMPTY_FILTER, type TaskFilter } from "@/lib/domain/filters";
import type { SortMode } from "@/lib/domain/sort";
import type { ProjectDTO, TagDTO, TaskDTO } from "@/lib/queries";

/**
 * One client-side store for the task list.
 *
 * Reads come from the server on every render; writes go through `useOptimistic`
 * so the UI moves at once and reconciles when the action's revalidation lands.
 * Every mutating helper here is fire-and-forget from the caller's point of
 * view — it paints, it persists, and it surfaces a toast if the server says no.
 */

type OptimisticAction =
  | { type: "toggle"; id: string; completed: boolean }
  | { type: "delete"; ids: string[] }
  | { type: "restore"; ids: string[] }
  | { type: "patch"; id: string; patch: Partial<TaskDTO> }
  | { type: "patchMany"; ids: string[]; patch: Partial<TaskDTO> }
  | { type: "reorder"; id: string; orderedIds: string[] }
  | { type: "create"; task: TaskDTO };

function reduce(tasks: TaskDTO[], action: OptimisticAction): TaskDTO[] {
  switch (action.type) {
    case "toggle":
      return tasks.map((task) =>
        task.id === action.id
          ? { ...task, completed: action.completed, completedAt: action.completed ? new Date() : null }
          : task,
      );
    case "delete":
      return tasks.filter((task) => !action.ids.includes(task.id));
    case "restore":
      return tasks;
    case "patch":
      return tasks.map((task) => (task.id === action.id ? { ...task, ...action.patch } : task));
    case "patchMany":
      return tasks.map((task) => (action.ids.includes(task.id) ? { ...task, ...action.patch } : task));
    case "reorder": {
      // Mirror the server's fractional-index maths so the row lands where it
      // was dropped instead of snapping back until the refetch arrives.
      const positions = action.orderedIds
        .filter((id) => id !== action.id)
        .map((id) => tasks.find((task) => task.id === id)?.position ?? 0);
      const toIndex = action.orderedIds.indexOf(action.id);
      const prev = toIndex > 0 ? positions[toIndex - 1] ?? null : null;
      const next = toIndex < positions.length ? positions[toIndex] ?? null : null;
      const position = computePosition(prev, next);
      return tasks.map((task) => (task.id === action.id ? { ...task, position } : task));
    }
    case "create":
      return [...tasks, action.task];
  }
}

interface AppStore {
  tasks: TaskDTO[];
  projects: ProjectDTO[];
  tags: TagDTO[];
  inbox: ProjectDTO | undefined;
  isPending: boolean;

  filter: TaskFilter;
  setFilter: React.Dispatch<React.SetStateAction<TaskFilter>>;
  sort: SortMode;
  setSort: (mode: SortMode) => void;

  selectedTaskId: string | null;
  setSelectedTaskId: (id: string | null) => void;

  /** Ids checked in the multi-select toolbar. */
  checkedIds: string[];
  toggleChecked: (id: string) => void;
  clearChecked: () => void;
  setCheckedIds: (ids: string[]) => void;

  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
  shortcutsOpen: boolean;
  setShortcutsOpen: (open: boolean) => void;
  quickAddSignal: number;
  focusQuickAdd: () => void;
  searchSignal: number;
  focusSearch: () => void;

  /** Announce a change to screen readers via the live region in the shell. */
  announce: (message: string) => void;
  announcement: string;

  add: (input: CreateTaskInput) => Promise<void>;
  toggle: (task: TaskDTO) => void;
  patch: (id: string, patch: Partial<TaskDTO>, persist?: Parameters<typeof updateTask>[0]) => void;
  remove: (task: TaskDTO) => void;
  move: (id: string, orderedIds: string[]) => void;
  completeChecked: () => void;
  deleteChecked: () => void;
  setCheckedPriority: (priority: number) => void;
}

const StoreContext = React.createContext<AppStore | null>(null);

export function useAppStore(): AppStore {
  const store = React.useContext(StoreContext);
  if (!store) throw new Error("useAppStore must be used inside <AppStoreProvider>");
  return store;
}

export function AppStoreProvider({
  tasks: serverTasks,
  projects,
  tags,
  children,
}: {
  tasks: TaskDTO[];
  projects: ProjectDTO[];
  tags: TagDTO[];
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [isPending, startTransition] = React.useTransition();
  const [tasks, applyOptimistic] = React.useOptimistic(serverTasks, reduce);

  /**
   * Pull the server's version of the list back down after a write.
   *
   * The actions call `revalidatePath`, but these routes render dynamically, so
   * there is no cache entry for it to invalidate and the action response comes
   * back without a new tree. Refreshing explicitly is what actually re-runs the
   * server components. It is called inside the same transition as the optimistic
   * update, so the optimistic state holds until the real data replaces it
   * instead of flickering back in between.
   */
  const refresh = React.useCallback(() => router.refresh(), [router]);

  const [filter, setFilter] = React.useState<TaskFilter>(EMPTY_FILTER);
  const [sort, setSort] = React.useState<SortMode>("manual");
  const [selectedTaskId, setSelectedTaskId] = React.useState<string | null>(null);
  const [checkedIds, setCheckedIds] = React.useState<string[]>([]);
  const [paletteOpen, setPaletteOpen] = React.useState(false);
  const [shortcutsOpen, setShortcutsOpen] = React.useState(false);
  const [quickAddSignal, setQuickAddSignal] = React.useState(0);
  const [searchSignal, setSearchSignal] = React.useState(0);
  const [announcement, setAnnouncement] = React.useState("");

  const announce = React.useCallback((message: string) => {
    // Clear first so repeating the same message is still announced.
    setAnnouncement("");
    requestAnimationFrame(() => setAnnouncement(message));
  }, []);

  const failed = React.useCallback((message: string) => {
    toast.error(message);
  }, []);

  const add = React.useCallback(
    async (input: CreateTaskInput) => {
      const result = await createTask(input);
      if (!result.ok) {
        failed(result.error);
        return;
      }
      refresh();
      announce(`Task added: ${input.title}`);
    },
    [announce, failed, refresh],
  );

  const toggle = React.useCallback(
    (task: TaskDTO) => {
      const completed = !task.completed;
      startTransition(async () => {
        applyOptimistic({ type: "toggle", id: task.id, completed });
        const result = await toggleTask(task.id, completed);
        if (!result.ok) {
          failed(result.error);
          return;
        }
        refresh();

        if (completed) {
          const repeated = Boolean(task.recurrence);
          toast.success(repeated ? "Completed · next one scheduled" : "Task completed", {
            description: task.title,
            action: {
              label: "Undo",
              onClick: () => {
                startTransition(async () => {
                  applyOptimistic({ type: "toggle", id: task.id, completed: false });
                  await undoToggle(task.id, result.spawnedTaskId, task.recurrence);
                  refresh();
                });
              },
            },
          });
        }
        announce(completed ? `Completed ${task.title}` : `Reopened ${task.title}`);
      });
    },
    [announce, applyOptimistic, failed, refresh],
  );

  const patch = React.useCallback(
    (id: string, optimistic: Partial<TaskDTO>, persist?: Parameters<typeof updateTask>[0]) => {
      startTransition(async () => {
        applyOptimistic({ type: "patch", id, patch: optimistic });
        const result = await updateTask(persist ?? { id, ...(optimistic as object) });
        if (!result.ok) failed(result.error);
        else refresh();
      });
    },
    [applyOptimistic, failed, refresh],
  );

  const remove = React.useCallback(
    (task: TaskDTO) => {
      startTransition(async () => {
        applyOptimistic({ type: "delete", ids: [task.id] });
        const result = await deleteTask(task.id);
        if (!result.ok) {
          failed(result.error);
          return;
        }
        refresh();
        toast("Task deleted", {
          description: task.title,
          action: {
            label: "Undo",
            onClick: () => {
              startTransition(async () => {
                await restoreTask(task.id);
                refresh();
              });
            },
          },
        });
        announce(`Deleted ${task.title}`);
      });
    },
    [announce, applyOptimistic, failed, refresh],
  );

  const move = React.useCallback(
    (id: string, orderedIds: string[]) => {
      startTransition(async () => {
        applyOptimistic({ type: "reorder", id, orderedIds });
        const result = await reorderTask({ id, orderedIds });
        if (!result.ok) failed(result.error);
        else refresh();
      });
    },
    [applyOptimistic, failed, refresh],
  );

  const toggleChecked = React.useCallback((id: string) => {
    setCheckedIds((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id],
    );
  }, []);

  const clearChecked = React.useCallback(() => setCheckedIds([]), []);

  const completeChecked = React.useCallback(() => {
    const ids = checkedIds;
    if (ids.length === 0) return;
    startTransition(async () => {
      applyOptimistic({ type: "patchMany", ids, patch: { completed: true, completedAt: new Date() } });
      await bulkComplete(ids);
      refresh();
      announce(`Completed ${ids.length} tasks`);
      toast.success(`${ids.length} tasks completed`);
    });
    setCheckedIds([]);
  }, [announce, applyOptimistic, checkedIds, refresh]);

  const deleteChecked = React.useCallback(() => {
    const ids = checkedIds;
    if (ids.length === 0) return;
    startTransition(async () => {
      applyOptimistic({ type: "delete", ids });
      await bulkDelete(ids);
      refresh();
      announce(`Deleted ${ids.length} tasks`);
      toast(`${ids.length} tasks deleted`, {
        action: {
          label: "Undo",
          onClick: () => {
            startTransition(async () => {
              for (const id of ids) await restoreTask(id);
              refresh();
            });
          },
        },
      });
    });
    setCheckedIds([]);
  }, [announce, applyOptimistic, checkedIds, refresh]);

  const setCheckedPriority = React.useCallback(
    (priority: number) => {
      const ids = checkedIds;
      if (ids.length === 0) return;
      startTransition(async () => {
        applyOptimistic({ type: "patchMany", ids, patch: { priority } });
        await bulkSetPriority(ids, priority);
        refresh();
      });
      setCheckedIds([]);
    },
    [applyOptimistic, checkedIds, refresh],
  );

  const value: AppStore = {
    tasks,
    projects,
    tags,
    inbox: projects.find((project) => project.isInbox),
    isPending,
    filter,
    setFilter,
    sort,
    setSort,
    selectedTaskId,
    setSelectedTaskId,
    checkedIds,
    toggleChecked,
    clearChecked,
    setCheckedIds,
    paletteOpen,
    setPaletteOpen,
    shortcutsOpen,
    setShortcutsOpen,
    quickAddSignal,
    focusQuickAdd: React.useCallback(() => setQuickAddSignal((n) => n + 1), []),
    searchSignal,
    focusSearch: React.useCallback(() => setSearchSignal((n) => n + 1), []),
    announce,
    announcement,
    add,
    toggle,
    patch,
    remove,
    move,
    completeChecked,
    deleteChecked,
    setCheckedPriority,
  };

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

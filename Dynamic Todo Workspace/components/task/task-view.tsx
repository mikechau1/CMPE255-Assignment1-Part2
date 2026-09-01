"use client";

import {
  ArrowUpDown,
  CalendarCheck2,
  CheckCircle2,
  Filter,
  Flag,
  Inbox,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import * as React from "react";

import { useAppStore } from "@/components/app-store";
import { EmptyState } from "@/components/task/empty-state";
import { QuickAdd } from "@/components/task/quick-add";
import { TaskList } from "@/components/task/task-list";
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Chip,
} from "@/components/ui";
import { accentClasses } from "@/lib/accent";
import { isFilterActive, matchesFilter, matchesView, type ViewId } from "@/lib/domain/filters";
import { SORT_LABELS, SORT_MODES, sortTasks, type SortMode } from "@/lib/domain/sort";
import { PRIORITY_META, type Priority } from "@/lib/domain/types";
import { useHotkeys } from "@/lib/hooks/use-hotkeys";
import { cn } from "@/lib/utils";

const EMPTY_STATES: Record<ViewId | "project", { icon: typeof Inbox; title: string; description: string }> = {
  today: {
    icon: CalendarCheck2,
    title: "Nothing left for today",
    description: "Everything due today is done. Anything overdue would show up here too.",
  },
  upcoming: {
    icon: Sparkles,
    title: "The next week is clear",
    description: "Tasks due in the next seven days will appear here, grouped by day.",
  },
  all: {
    icon: Inbox,
    title: "No open tasks",
    description: "Add one above — try “Pay rent tomorrow 5pm #Home !p1”.",
  },
  completed: {
    icon: CheckCircle2,
    title: "Nothing completed yet",
    description: "Tasks you tick off will collect here.",
  },
  trash: {
    icon: X,
    title: "Trash is empty",
    description: "Deleted tasks rest here until you empty it.",
  },
  project: {
    icon: Inbox,
    title: "This project is empty",
    description: "Add the first task above.",
  },
};

export function TaskView({
  view,
  title,
  subtitle,
  projectId,
  groupByDate,
}: {
  view: ViewId;
  title: string;
  subtitle?: string;
  projectId?: string;
  groupByDate?: boolean;
}) {
  const store = useAppStore();
  const searchRef = React.useRef<HTMLInputElement>(null);
  const [activeIndex, setActiveIndex] = React.useState(-1);

  React.useEffect(() => {
    if (store.searchSignal > 0) searchRef.current?.focus();
  }, [store.searchSignal]);

  const now = React.useMemo(() => new Date(), []);

  const visible = React.useMemo(() => {
    const filter = projectId ? { ...store.filter, projectId } : store.filter;
    const matched = store.tasks.filter(
      (task) => matchesView(task, view, now) && matchesFilter(task, filter, now),
    );
    return sortTasks(matched, store.sort);
  }, [now, projectId, store.filter, store.sort, store.tasks, view]);

  // Keep the keyboard cursor inside the list as it grows and shrinks.
  React.useEffect(() => {
    setActiveIndex((index) => (index >= visible.length ? visible.length - 1 : index));
  }, [visible.length]);

  const activeTask = activeIndex >= 0 ? visible[activeIndex] : undefined;

  const moveCursor = React.useCallback(
    (delta: number) => {
      setActiveIndex((index) => {
        const next = Math.min(Math.max(index + delta, 0), visible.length - 1);
        document
          .querySelector(`[data-task-id="${visible[next]?.id}"]`)
          ?.scrollIntoView({ block: "nearest" });
        return next;
      });
    },
    [visible],
  );

  useHotkeys({
    j: () => moveCursor(1),
    k: () => moveCursor(-1),
    ArrowDown: () => activeIndex >= 0 && moveCursor(1),
    ArrowUp: () => activeIndex >= 0 && moveCursor(-1),
    " ": () => activeTask && store.toggle(activeTask),
    Enter: () => activeTask && store.setSelectedTaskId(activeTask.id),
    e: () => activeTask && store.setSelectedTaskId(activeTask.id),
    x: () => activeTask && store.toggleChecked(activeTask.id),
    "#": () => activeTask && store.remove(activeTask),
    "1": () => activeTask && store.patch(activeTask.id, { priority: 3 }, { id: activeTask.id, priority: 3 }),
    "2": () => activeTask && store.patch(activeTask.id, { priority: 2 }, { id: activeTask.id, priority: 2 }),
    "3": () => activeTask && store.patch(activeTask.id, { priority: 1 }, { id: activeTask.id, priority: 1 }),
    "4": () => activeTask && store.patch(activeTask.id, { priority: 0 }, { id: activeTask.id, priority: 0 }),
  });

  const filterActive = isFilterActive(projectId ? { ...store.filter, projectId: null } : store.filter);
  const emptyKey = projectId ? "project" : view;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 lg:py-10">
      <header className="mb-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="text-sm text-muted-foreground" data-testid="task-count">
            {visible.length} {visible.length === 1 ? "task" : "tasks"}
          </p>
        </div>
        {subtitle ? <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p> : null}
      </header>

      {view !== "completed" && view !== "trash" ? (
        <div className="mb-5">
          <QuickAdd projectId={projectId} />
        </div>
      ) : null}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle-foreground" />
          <input
            ref={searchRef}
            type="search"
            value={store.filter.search ?? ""}
            onChange={(event) =>
              store.setFilter((current) => ({ ...current, search: event.target.value }))
            }
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                store.setFilter((current) => ({ ...current, search: "" }));
                event.currentTarget.blur();
              }
            }}
            placeholder="Search tasks…"
            aria-label="Search tasks"
            className={cn(
              "h-9 w-full rounded-lg bg-surface pl-9 pr-3 text-sm ring-1 ring-border",
              "placeholder:text-subtle-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          />
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="secondary">
              <Filter className="size-4" />
              <span className="hidden sm:inline">Filter</span>
              {filterActive ? <span className="size-1.5 rounded-full bg-accent" /> : null}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="min-w-52">
            <DropdownMenuItem
              onSelect={(event) => {
                event.preventDefault();
                store.setFilter((current) => ({ ...current, overdueOnly: !current.overdueOnly }));
              }}
            >
              <Flag className="size-4 text-danger" />
              Overdue only
              {store.filter.overdueOnly ? <span className="ml-auto text-accent">✓</span> : null}
            </DropdownMenuItem>

            <DropdownMenuSeparator />
            {([3, 2, 1, 0] as Priority[]).map((value) => {
              const active = store.filter.priorities?.includes(value) ?? false;
              return (
                <DropdownMenuItem
                  key={value}
                  onSelect={(event) => {
                    event.preventDefault();
                    store.setFilter((current) => {
                      const priorities = current.priorities ?? [];
                      return {
                        ...current,
                        priorities: active
                          ? priorities.filter((p) => p !== value)
                          : [...priorities, value],
                      };
                    });
                  }}
                >
                  <Flag className={cn("size-4 fill-current", PRIORITY_META[value].className)} />
                  {PRIORITY_META[value].label}
                  {active ? <span className="ml-auto text-accent">✓</span> : null}
                </DropdownMenuItem>
              );
            })}

            {store.tags.length ? (
              <>
                <DropdownMenuSeparator />
                {store.tags.map((tag) => {
                  const active = store.filter.tagIds?.includes(tag.id) ?? false;
                  return (
                    <DropdownMenuItem
                      key={tag.id}
                      onSelect={(event) => {
                        event.preventDefault();
                        store.setFilter((current) => {
                          const tagIds = current.tagIds ?? [];
                          return {
                            ...current,
                            tagIds: active ? tagIds.filter((id) => id !== tag.id) : [...tagIds, tag.id],
                          };
                        });
                      }}
                    >
                      <span className={cn("size-2 rounded-full", accentClasses(tag.color).dot)} />
                      {tag.name}
                      {active ? <span className="ml-auto text-accent">✓</span> : null}
                    </DropdownMenuItem>
                  );
                })}
              </>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="secondary">
              <ArrowUpDown className="size-4" />
              <span className="hidden sm:inline">{SORT_LABELS[store.sort]}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            {SORT_MODES.map((mode: SortMode) => (
              <DropdownMenuItem key={mode} onSelect={() => store.setSort(mode)}>
                {SORT_LABELS[mode]}
                {store.sort === mode ? <span className="ml-auto text-accent">✓</span> : null}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {filterActive ? (
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-subtle-foreground">Filtered</span>
          {store.filter.overdueOnly ? (
            <Chip className="bg-danger-soft text-danger ring-danger/20">Overdue</Chip>
          ) : null}
          {store.filter.priorities?.map((value) => (
            <Chip key={value} className="bg-surface-muted text-muted-foreground ring-border">
              {PRIORITY_META[value as Priority].label}
            </Chip>
          ))}
          {store.filter.tagIds?.map((id) => {
            const tag = store.tags.find((candidate) => candidate.id === id);
            return tag ? (
              <Chip key={id} className={accentClasses(tag.color).chip}>
                {tag.name}
              </Chip>
            ) : null;
          })}
          <Button
            size="sm"
            variant="ghost"
            className="h-6 px-1.5 text-xs"
            onClick={() => store.setFilter({ search: store.filter.search })}
          >
            Clear
          </Button>
        </div>
      ) : null}

      <TaskList
        tasks={visible}
        groupByDate={groupByDate && store.sort === "manual"}
        activeId={activeTask?.id ?? null}
        emptyState={
          store.filter.search?.trim() || filterActive ? (
            <EmptyState
              icon={Search}
              title="No matching tasks"
              description="Try a different search, or clear the filters above."
            />
          ) : (
            <EmptyState {...EMPTY_STATES[emptyKey]} />
          )
        }
      />
    </div>
  );
}

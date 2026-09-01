"use client";

import { Command } from "cmdk";
import {
  BarChart3,
  CalendarDays,
  CheckCircle2,
  Keyboard,
  LayoutList,
  Moon,
  Plus,
  Search,
  Sun,
  Trash2,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import * as React from "react";

import { useAppStore } from "@/components/app-store";
import { Dialog, DialogDescription, DialogTitle, Kbd } from "@/components/ui";
import { accentClasses } from "@/lib/accent";
import { formatDueDate } from "@/lib/domain/dates";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cn } from "@/lib/utils";

/**
 * ⌘K palette: jump to a view or project, run an action, or find a task by name.
 *
 * cmdk handles the filtering and the roving focus; this only supplies the items
 * and what each one does.
 */
export function CommandPalette() {
  const store = useAppStore();
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const [query, setQuery] = React.useState("");

  const close = React.useCallback(() => {
    store.setPaletteOpen(false);
    setQuery("");
  }, [store]);

  const run = React.useCallback(
    (action: () => void) => {
      close();
      // Let the dialog finish closing before moving focus somewhere else.
      requestAnimationFrame(action);
    },
    [close],
  );

  const openTasks = store.tasks.filter((task) => !task.completed).slice(0, 200);

  return (
    <Dialog open={store.paletteOpen} onOpenChange={(open) => (open ? store.setPaletteOpen(true) : close())}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 animate-fade-in bg-[var(--overlay)] backdrop-blur-[2px]" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className={cn(
            "fixed left-1/2 top-[12vh] z-50 w-[min(38rem,calc(100vw-2rem))] -translate-x-1/2",
            "animate-slide-up overflow-hidden rounded-xl bg-surface shadow-2xl ring-1 ring-border focus:outline-none",
          )}
        >
          <DialogTitle className="sr-only">Command palette</DialogTitle>
          <DialogDescription className="sr-only">
            Search tasks, jump to a view, or run a command.
          </DialogDescription>

          <Command loop label="Command palette" className="flex flex-col">
            <div className="flex items-center gap-2.5 border-b border-border px-4">
              <Search className="size-4 shrink-0 text-subtle-foreground" />
              <Command.Input
                value={query}
                onValueChange={setQuery}
                placeholder="Search tasks or type a command…"
                className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-subtle-foreground"
              />
              <Kbd>Esc</Kbd>
            </div>

            <Command.List className="scrollbar-thin max-h-[52vh] overflow-y-auto p-2">
              <Command.Empty className="px-3 py-8 text-center text-sm text-muted-foreground">
                Nothing matches “{query}”.
              </Command.Empty>

              <Group heading="Actions">
                <Item onSelect={() => run(store.focusQuickAdd)} icon={<Plus className="size-4" />}>
                  Add a task
                  <Kbd className="ml-auto">n</Kbd>
                </Item>
                <Item onSelect={() => run(store.focusSearch)} icon={<Search className="size-4" />}>
                  Search this view
                  <Kbd className="ml-auto">/</Kbd>
                </Item>
                <Item
                  onSelect={() => run(() => setTheme(resolvedTheme === "dark" ? "light" : "dark"))}
                  icon={resolvedTheme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
                >
                  Switch to {resolvedTheme === "dark" ? "light" : "dark"} mode
                </Item>
                <Item
                  onSelect={() => run(() => store.setShortcutsOpen(true))}
                  icon={<Keyboard className="size-4" />}
                >
                  Keyboard shortcuts
                  <Kbd className="ml-auto">?</Kbd>
                </Item>
              </Group>

              <Group heading="Go to">
                <Item onSelect={() => run(() => router.push("/today"))} icon={<Sun className="size-4" />}>
                  Today
                </Item>
                <Item
                  onSelect={() => run(() => router.push("/upcoming"))}
                  icon={<CalendarDays className="size-4" />}
                >
                  Upcoming
                </Item>
                <Item onSelect={() => run(() => router.push("/all"))} icon={<LayoutList className="size-4" />}>
                  All tasks
                </Item>
                <Item
                  onSelect={() => run(() => router.push("/completed"))}
                  icon={<CheckCircle2 className="size-4" />}
                >
                  Completed
                </Item>
                <Item onSelect={() => run(() => router.push("/stats"))} icon={<BarChart3 className="size-4" />}>
                  Stats
                </Item>
                <Item onSelect={() => run(() => router.push("/trash"))} icon={<Trash2 className="size-4" />}>
                  Trash
                </Item>
              </Group>

              <Group heading="Projects">
                {store.projects.map((project) => (
                  <Item
                    key={project.id}
                    onSelect={() => run(() => router.push(`/project/${project.id}`))}
                    icon={
                      project.emoji ? (
                        <span className="text-sm leading-none">{project.emoji}</span>
                      ) : (
                        <span className={cn("size-2 rounded-full", accentClasses(project.color).dot)} />
                      )
                    }
                  >
                    {project.name}
                    <span className="ml-auto text-xs text-subtle-foreground">{project.openCount}</span>
                  </Item>
                ))}
              </Group>

              <Group heading="Tasks">
                {openTasks.map((task) => (
                  <Item
                    key={task.id}
                    value={`${task.title} ${task.notes ?? ""}`}
                    onSelect={() => run(() => store.setSelectedTaskId(task.id))}
                    icon={<span className="size-1.5 rounded-full bg-border-strong" />}
                  >
                    <span className="truncate">{task.title}</span>
                    {task.dueDate ? (
                      <span className="ml-auto shrink-0 text-xs text-subtle-foreground">
                        {formatDueDate(task.dueDate, task.hasTime)}
                      </span>
                    ) : null}
                  </Item>
                ))}
              </Group>
            </Command.List>
          </Command>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </Dialog>
  );
}

function Group({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Command.Group
      heading={heading}
      className="mb-1 [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-subtle-foreground"
    >
      {children}
    </Command.Group>
  );
}

function Item({
  icon,
  children,
  onSelect,
  value,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
  onSelect: () => void;
  value?: string;
}) {
  return (
    <Command.Item
      value={value}
      onSelect={onSelect}
      className={cn(
        "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-foreground",
        "data-[selected=true]:bg-accent-soft data-[selected=true]:text-accent",
      )}
    >
      <span className="grid w-4 shrink-0 place-items-center text-muted-foreground">{icon}</span>
      {children}
    </Command.Item>
  );
}

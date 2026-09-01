"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useRouter } from "next/navigation";
import { Check, Flag, Plus, Repeat, Trash2, X } from "lucide-react";
import * as React from "react";

import { createTask, deleteTask, toggleTask } from "@/app/actions/tasks";
import { loadSubtasks } from "@/app/actions/reads";
import { useAppStore } from "@/components/app-store";
import { Button, Checkbox, Input, Textarea, Chip } from "@/components/ui";
import { accentClasses } from "@/lib/accent";
import { fromDateInputValue, toDateInputValue, toTimeInputValue } from "@/lib/domain/dates";
import {
  RECURRENCE_PRESETS,
  describeRecurrence,
  parseRecurrence,
  type RecurrenceRule,
} from "@/lib/domain/recurrence";
import { PRIORITIES, PRIORITY_META, type Priority } from "@/lib/domain/types";
import type { TaskDTO } from "@/lib/queries";
import { cn } from "@/lib/utils";

/**
 * The slide-over for one task.
 *
 * It edits in place: each field commits on blur or on change rather than behind
 * a Save button, so there is no half-saved state to reason about and Escape is
 * always safe.
 */
export function TaskDetailPanel() {
  const store = useAppStore();
  const task = store.tasks.find((candidate) => candidate.id === store.selectedTaskId) ?? null;
  const open = Boolean(task);

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(next) => !next && store.setSelectedTaskId(null)}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 animate-fade-in bg-[var(--overlay)] md:bg-transparent" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className={cn(
            "fixed inset-y-0 right-0 z-50 flex w-full max-w-md animate-slide-in-right flex-col",
            "border-l border-border bg-surface shadow-2xl focus:outline-none",
          )}
        >
          {task ? <PanelBody key={task.id} task={task} /> : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function PanelBody({ task }: { task: TaskDTO }) {
  const store = useAppStore();
  const router = useRouter();
  const [title, setTitle] = React.useState(task.title);
  const [notes, setNotes] = React.useState(task.notes ?? "");
  const [subtasks, setSubtasks] = React.useState<TaskDTO[] | null>(null);
  const [newSubtask, setNewSubtask] = React.useState("");

  const rule = parseRecurrence(task.recurrence);

  const refreshSubtasks = React.useCallback(() => {
    loadSubtasks(task.id).then(setSubtasks);
    // The task row shows a done/total counter, so the list behind the panel
    // has to be refetched too.
    router.refresh();
  }, [router, task.id]);

  React.useEffect(() => {
    refreshSubtasks();
  }, [refreshSubtasks]);

  function commitTitle() {
    const trimmed = title.trim();
    if (!trimmed || trimmed === task.title) {
      setTitle(task.title);
      return;
    }
    store.patch(task.id, { title: trimmed }, { id: task.id, title: trimmed });
  }

  function commitNotes() {
    const value = notes.trim() || null;
    if (value === (task.notes ?? null)) return;
    store.patch(task.id, { notes: value }, { id: task.id, notes: value });
  }

  function setDue(dateValue: string, timeValue: string) {
    const day = fromDateInputValue(dateValue);
    if (!day) {
      store.patch(task.id, { dueDate: null, hasTime: false }, { id: task.id, dueDate: null, hasTime: false });
      return;
    }
    const dueDate = new Date(day);
    const hasTime = Boolean(timeValue);
    if (hasTime) {
      const [hours, minutes] = timeValue.split(":").map(Number);
      dueDate.setHours(hours ?? 0, minutes ?? 0, 0, 0);
    }
    store.patch(task.id, { dueDate, hasTime }, { id: task.id, dueDate, hasTime });
  }

  function setRecurrence(next: RecurrenceRule | null) {
    store.patch(
      task.id,
      { recurrence: next ? JSON.stringify(next) : null },
      { id: task.id, recurrence: next },
    );
  }

  function toggleTag(tagId: string) {
    const tagIds = task.tagIds.includes(tagId)
      ? task.tagIds.filter((id) => id !== tagId)
      : [...task.tagIds, tagId];
    const tags = store.tags.filter((tag) => tagIds.includes(tag.id));
    store.patch(task.id, { tagIds, tags }, { id: task.id, tagIds });
  }

  async function addSubtask(event: React.FormEvent) {
    event.preventDefault();
    const value = newSubtask.trim();
    if (!value) return;
    setNewSubtask("");
    await createTask({ title: value, parentId: task.id });
    refreshSubtasks();
  }

  return (
    <>
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <DialogPrimitive.Title className="text-sm font-semibold text-muted-foreground">
          Task details
        </DialogPrimitive.Title>
        <div className="flex items-center gap-1">
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="Delete task"
            onClick={() => {
              store.setSelectedTaskId(null);
              store.remove(task);
            }}
          >
            <Trash2 className="size-4" />
          </Button>
          <DialogPrimitive.Close asChild>
            <Button size="icon-sm" variant="ghost" aria-label="Close details">
              <X className="size-4" />
            </Button>
          </DialogPrimitive.Close>
        </div>
      </header>

      <div className="scrollbar-thin flex-1 space-y-6 overflow-y-auto px-4 py-4">
        <div className="flex items-start gap-3">
          <Checkbox
            checked={task.completed}
            onCheckedChange={() => store.toggle(task)}
            aria-label={task.completed ? "Reopen task" : "Complete task"}
            className="mt-1.5"
          />
          <textarea
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            onBlur={commitTitle}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                event.currentTarget.blur();
              }
            }}
            rows={Math.max(1, Math.ceil(title.length / 38))}
            aria-label="Task title"
            className={cn(
              "flex-1 resize-none rounded-lg bg-transparent px-1 py-1 text-base font-medium leading-snug",
              "text-foreground outline-none focus-visible:bg-surface-muted",
              task.completed && "line-through opacity-60",
            )}
          />
        </div>

        <Field label="Notes">
          <Textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            onBlur={commitNotes}
            rows={4}
            aria-label="Notes"
            placeholder="Add details, links, or context…"
          />
        </Field>

        <Field label="Due">
          <div className="flex gap-2">
            <Input
              type="date"
              aria-label="Due date"
              value={toDateInputValue(task.dueDate)}
              onChange={(event) => setDue(event.target.value, toTimeInputValue(task.dueDate, task.hasTime))}
            />
            <Input
              type="time"
              aria-label="Due time"
              className="w-32"
              disabled={!task.dueDate}
              value={toTimeInputValue(task.dueDate, task.hasTime)}
              onChange={(event) => setDue(toDateInputValue(task.dueDate), event.target.value)}
            />
          </div>
          {task.dueDate && !task.hasTime ? (
            <p className="mt-1.5 text-xs text-subtle-foreground">
              All day — it will not count as overdue until the day is out.
            </p>
          ) : null}
        </Field>

        <Field label="Priority">
          <div className="flex gap-1.5">
            {([...PRIORITIES] as Priority[]).reverse().map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => store.patch(task.id, { priority: value }, { id: task.id, priority: value })}
                aria-pressed={task.priority === value}
                className={cn(
                  "inline-flex h-8 flex-1 items-center justify-center gap-1.5 rounded-lg text-xs font-medium",
                  "ring-1 ring-border transition-colors hover:bg-surface-muted",
                  task.priority === value && "bg-accent-soft ring-accent/40",
                )}
              >
                <Flag className={cn("size-3.5 fill-current", PRIORITY_META[value].className)} />
                {PRIORITY_META[value].label}
              </button>
            ))}
          </div>
        </Field>

        <Field label="Project">
          <select
            aria-label="Project"
            value={task.projectId ?? ""}
            onChange={(event) =>
              store.patch(
                task.id,
                { projectId: event.target.value },
                { id: task.id, projectId: event.target.value },
              )
            }
            className="h-9 w-full rounded-lg bg-surface px-2.5 text-sm ring-1 ring-border focus-visible:ring-2 focus-visible:ring-ring"
          >
            {store.projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.emoji ? `${project.emoji} ` : ""}
                {project.name}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Tags">
          <div className="flex flex-wrap gap-1.5">
            {store.tags.map((tag) => {
              const active = task.tagIds.includes(tag.id);
              return (
                <button key={tag.id} type="button" onClick={() => toggleTag(tag.id)} aria-pressed={active}>
                  <Chip
                    className={cn(
                      "cursor-pointer transition-opacity",
                      active ? accentClasses(tag.color).chip : "bg-surface-muted text-muted-foreground ring-border opacity-70 hover:opacity-100",
                    )}
                  >
                    {active ? <Check className="size-3" /> : null}
                    {tag.name}
                  </Chip>
                </button>
              );
            })}
            {store.tags.length === 0 ? (
              <p className="text-xs text-subtle-foreground">
                No tags yet — add one from quick add with @name.
              </p>
            ) : null}
          </div>
        </Field>

        <Field label="Repeat">
          <div className="flex flex-wrap gap-1.5">
            <RepeatOption active={!rule} onClick={() => setRecurrence(null)}>
              Never
            </RepeatOption>
            {RECURRENCE_PRESETS.map((preset) => (
              <RepeatOption
                key={preset.id}
                active={Boolean(rule) && describeRecurrence(rule) === describeRecurrence(preset.rule)}
                onClick={() => setRecurrence(preset.rule)}
              >
                {preset.label}
              </RepeatOption>
            ))}
          </div>
          {rule ? (
            <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <Repeat className="size-3.5" />
              {describeRecurrence(rule)} — completing this schedules the next one.
            </p>
          ) : null}
        </Field>

        <Field
          label={`Subtasks${subtasks?.length ? ` · ${subtasks.filter((s) => s.completed).length}/${subtasks.length}` : ""}`}
        >
          {subtasks === null ? (
            <p className="text-xs text-subtle-foreground">Loading…</p>
          ) : (
            <ul className="space-y-1">
              {subtasks.map((subtask) => (
                <li key={subtask.id} className="group/sub flex items-center gap-2.5 rounded-lg px-1 py-1">
                  <Checkbox
                    checked={subtask.completed}
                    aria-label={`Complete ${subtask.title}`}
                    onCheckedChange={async () => {
                      setSubtasks((current) =>
                        current?.map((item) =>
                          item.id === subtask.id ? { ...item, completed: !item.completed } : item,
                        ) ?? null,
                      );
                      await toggleTask(subtask.id, !subtask.completed);
                      refreshSubtasks();
                    }}
                  />
                  <span
                    className={cn(
                      "flex-1 text-sm",
                      subtask.completed && "text-muted-foreground line-through",
                    )}
                  >
                    {subtask.title}
                  </span>
                  <button
                    type="button"
                    aria-label={`Delete ${subtask.title}`}
                    onClick={async () => {
                      setSubtasks((current) => current?.filter((item) => item.id !== subtask.id) ?? null);
                      await deleteTask(subtask.id);
                      refreshSubtasks();
                    }}
                    className="opacity-0 transition-opacity group-hover/sub:opacity-100 focus-visible:opacity-100"
                  >
                    <X className="size-3.5 text-muted-foreground" />
                  </button>
                </li>
              ))}
            </ul>
          )}

          <form onSubmit={addSubtask} className="mt-2 flex items-center gap-2">
            <Plus className="size-4 text-subtle-foreground" />
            <input
              value={newSubtask}
              onChange={(event) => setNewSubtask(event.target.value)}
              placeholder="Add a subtask"
              aria-label="Add a subtask"
              className="flex-1 bg-transparent py-1 text-sm outline-none placeholder:text-subtle-foreground"
            />
          </form>
        </Field>
      </div>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-subtle-foreground">
        {label}
      </h3>
      {children}
    </section>
  );
}

function RepeatOption({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-lg px-2.5 py-1 text-xs font-medium ring-1 ring-border transition-colors hover:bg-surface-muted",
        active && "bg-accent-soft ring-accent/40",
      )}
    >
      {children}
    </button>
  );
}

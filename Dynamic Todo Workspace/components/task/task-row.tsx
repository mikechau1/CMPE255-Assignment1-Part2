"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  CalendarClock,
  Check,
  Flag,
  GripVertical,
  ListTree,
  MoreHorizontal,
  Pencil,
  Repeat,
  Trash2,
} from "lucide-react";
import * as React from "react";

import { useAppStore } from "@/components/app-store";
import {
  Checkbox,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Chip,
} from "@/components/ui";
import { accentClasses } from "@/lib/accent";
import { dueTone, formatDueDate } from "@/lib/domain/dates";
import { describeRecurrence, parseRecurrence } from "@/lib/domain/recurrence";
import { highlightSegments } from "@/lib/domain/search";
import { PRIORITY_META, type Priority } from "@/lib/domain/types";
import type { TaskDTO } from "@/lib/queries";
import { cn } from "@/lib/utils";

const DUE_TONE_CLASSES = {
  overdue: "text-danger",
  today: "text-accent",
  soon: "text-warning",
  later: "text-muted-foreground",
  none: "text-muted-foreground",
} as const;

export interface TaskRowProps {
  task: TaskDTO;
  /** Highlights the row under keyboard navigation. */
  active?: boolean;
  sortable?: boolean;
  onActivate?: () => void;
}

export const TaskRow = React.memo(function TaskRow({
  task,
  active,
  sortable = true,
  onActivate,
}: TaskRowProps) {
  const store = useAppStore();
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id, disabled: !sortable });

  const project = store.projects.find((candidate) => candidate.id === task.projectId);
  const rule = parseRecurrence(task.recurrence);
  const tone = dueTone(task);
  const priority = PRIORITY_META[(task.priority as Priority) ?? 0];
  const isChecked = store.checkedIds.includes(task.id);
  const search = store.filter.search ?? "";

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      data-testid="task-row"
      data-task-id={task.id}
      data-completed={task.completed ? "true" : "false"}
      className={cn(
        "group/row relative flex items-start gap-3 rounded-xl px-2.5 py-2.5 transition-colors",
        "hover:bg-surface-muted",
        active && "bg-surface-muted ring-1 ring-accent/40",
        isChecked && "bg-accent-soft/60",
        isDragging && "z-10 opacity-90 shadow-lg ring-1 ring-border",
        task.completed && "opacity-55",
      )}
    >
      {sortable ? (
        <button
          ref={setActivatorNodeRef}
          {...attributes}
          {...listeners}
          aria-label={`Reorder ${task.title}`}
          className={cn(
            "absolute -left-5 top-3 hidden cursor-grab text-subtle-foreground",
            "group-hover/row:block focus-visible:block active:cursor-grabbing md:block md:opacity-0",
            "md:group-hover/row:opacity-100 md:focus-visible:opacity-100",
          )}
        >
          <GripVertical className="size-4" />
        </button>
      ) : null}

      <Checkbox
        checked={task.completed}
        onCheckedChange={() => store.toggle(task)}
        aria-label={task.completed ? `Reopen ${task.title}` : `Complete ${task.title}`}
        className="mt-0.5"
      />

      <div className="min-w-0 flex-1">
        <button
          type="button"
          onClick={onActivate ?? (() => store.setSelectedTaskId(task.id))}
          className="block w-full text-left"
        >
          <span
            className={cn(
              "text-sm leading-snug text-foreground",
              task.completed && "line-through decoration-muted-foreground",
            )}
          >
            {highlightSegments(task.title, search).map((segment, index) =>
              segment.match ? (
                <mark key={index} className="rounded bg-warning/30 text-foreground">
                  {segment.text}
                </mark>
              ) : (
                <React.Fragment key={index}>{segment.text}</React.Fragment>
              ),
            )}
          </span>
        </button>

        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {task.dueDate ? (
            <span className={cn("inline-flex items-center gap-1", DUE_TONE_CLASSES[tone])}>
              <CalendarClock className="size-3.5" />
              {formatDueDate(task.dueDate, task.hasTime)}
            </span>
          ) : null}

          {rule ? (
            <span
              className="inline-flex items-center gap-1 text-muted-foreground"
              title={describeRecurrence(rule)}
            >
              <Repeat className="size-3.5" />
              {describeRecurrence(rule)}
            </span>
          ) : null}

          {task.subtaskTotal > 0 ? (
            <span className="inline-flex items-center gap-1 text-muted-foreground">
              <ListTree className="size-3.5" />
              {task.subtaskDone}/{task.subtaskTotal}
            </span>
          ) : null}

          {task.priority > 0 ? (
            <span className={cn("inline-flex items-center gap-1", priority.className)}>
              <Flag className="size-3.5 fill-current" />
              {priority.label}
            </span>
          ) : null}

          {task.tags.map((tag) => (
            <Chip key={tag.id} className={accentClasses(tag.color).chip}>
              {tag.name}
            </Chip>
          ))}

          {project && !project.isInbox ? (
            <span className="ml-auto inline-flex items-center gap-1.5 text-muted-foreground">
              <span className={cn("size-1.5 rounded-full", accentClasses(project.color).dot)} />
              {project.name}
            </span>
          ) : null}
        </div>
      </div>

      <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover/row:opacity-100 focus-within:opacity-100">
        <button
          type="button"
          onClick={() => store.toggleChecked(task.id)}
          aria-label={isChecked ? `Deselect ${task.title}` : `Select ${task.title}`}
          aria-pressed={isChecked}
          className={cn(
            "grid size-7 place-items-center rounded-md text-muted-foreground hover:bg-border/60",
            isChecked && "text-accent opacity-100",
          )}
        >
          <Check className="size-4" />
        </button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label={`More actions for ${task.title}`}
              className="grid size-7 place-items-center rounded-md text-muted-foreground hover:bg-border/60"
            >
              <MoreHorizontal className="size-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onSelect={() => store.setSelectedTaskId(task.id)}>
              <Pencil className="size-4" />
              Edit details
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            {([3, 2, 1, 0] as Priority[]).map((value) => (
              <DropdownMenuItem
                key={value}
                onSelect={() => store.patch(task.id, { priority: value }, { id: task.id, priority: value })}
              >
                <Flag className={cn("size-4", PRIORITY_META[value].className)} />
                {PRIORITY_META[value].label}
                {task.priority === value ? <Check className="ml-auto size-3.5" /> : null}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive onSelect={() => store.remove(task)}>
              <Trash2 className="size-4" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </li>
  );
});

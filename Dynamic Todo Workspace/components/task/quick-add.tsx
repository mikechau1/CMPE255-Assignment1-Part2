"use client";

import { CalendarClock, Flag, Hash, Plus, Repeat, Tag as TagIcon } from "lucide-react";
import * as React from "react";

import { useAppStore } from "@/components/app-store";
import { Button, Chip, Kbd } from "@/components/ui";
import { formatDueDate } from "@/lib/domain/dates";
import { parseQuickAdd, type ParsedQuickAdd } from "@/lib/domain/quick-add";
import { describeRecurrence } from "@/lib/domain/recurrence";
import { PRIORITY_META, type Priority } from "@/lib/domain/types";
import { cn } from "@/lib/utils";

const EXAMPLES = [
  "Pay rent tomorrow 5pm #Home !p1",
  "Read chapter 4 friday @reading",
  "Standup every weekday at 9",
];

/**
 * The primary way tasks get created.
 *
 * The input is plain text; everything structured about the task is inferred as
 * you type and previewed underneath, so the tokens are discoverable without a
 * manual and nothing is committed to until Enter.
 */
export function QuickAdd({
  projectId,
  placeholder = "Add a task…",
  autoFocus,
}: {
  projectId?: string | null;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const store = useAppStore();
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [value, setValue] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [exampleIndex, setExampleIndex] = React.useState(0);

  // The "n" shortcut and the command palette both focus this input.
  React.useEffect(() => {
    if (store.quickAddSignal > 0) inputRef.current?.focus();
  }, [store.quickAddSignal]);

  React.useEffect(() => {
    if (value) return;
    const timer = setInterval(() => setExampleIndex((index) => (index + 1) % EXAMPLES.length), 4200);
    return () => clearInterval(timer);
  }, [value]);

  const parsed = React.useMemo<ParsedQuickAdd | null>(
    () => (value.trim() ? parseQuickAdd(value) : null),
    [value],
  );

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!parsed || !parsed.title.trim() || submitting) return;

    setSubmitting(true);
    const snapshot = value;
    setValue("");

    try {
      await store.add({
        title: parsed.title,
        dueDate: parsed.dueDate,
        hasTime: parsed.hasTime,
        priority: parsed.priority,
        projectName: parsed.projectName,
        projectId: parsed.projectName ? null : projectId ?? null,
        tagNames: parsed.tagNames,
        recurrence: parsed.recurrence,
      });
    } catch {
      // Put the text back so nothing typed is lost.
      setValue(snapshot);
    } finally {
      setSubmitting(false);
      inputRef.current?.focus();
    }
  }

  const hasTokens =
    parsed &&
    (parsed.dueDate ||
      parsed.priority > 0 ||
      parsed.projectName ||
      parsed.tagNames.length > 0 ||
      parsed.recurrence);

  return (
    <form onSubmit={submit} className="group/quickadd">
      <div
        className={cn(
          "flex items-center gap-2.5 rounded-xl bg-surface px-3 py-2 ring-1 ring-border transition-shadow",
          "focus-within:ring-2 focus-within:ring-ring",
        )}
      >
        <Plus className="size-4 shrink-0 text-subtle-foreground" />
        <input
          ref={inputRef}
          value={value}
          autoFocus={autoFocus}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setValue("");
              inputRef.current?.blur();
            }
          }}
          placeholder={value ? placeholder : `${placeholder}  e.g. ${EXAMPLES[exampleIndex]}`}
          aria-label="Add a task"
          aria-describedby="quick-add-hint"
          className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-subtle-foreground"
        />
        {value ? (
          <Button type="submit" size="sm" variant="primary" disabled={!parsed?.title.trim() || submitting}>
            Add
            <Kbd className="bg-white/15 text-current">↵</Kbd>
          </Button>
        ) : (
          <Kbd className="hidden sm:inline-flex">n</Kbd>
        )}
      </div>

      {hasTokens ? (
        <div
          data-testid="quick-add-preview"
          className="mt-2 flex animate-slide-up flex-wrap items-center gap-1.5 px-1 text-xs"
          aria-live="polite"
        >
          <span className="text-subtle-foreground">Will create:</span>
          <span className="font-medium text-foreground">{parsed!.title || "…"}</span>

          {parsed!.dueDate ? (
            <Chip className="bg-accent-soft text-accent ring-accent/20">
              <CalendarClock className="size-3" />
              {formatDueDate(parsed!.dueDate, parsed!.hasTime)}
            </Chip>
          ) : null}
          {parsed!.recurrence ? (
            <Chip className="bg-surface-muted text-muted-foreground ring-border">
              <Repeat className="size-3" />
              {describeRecurrence(parsed!.recurrence)}
            </Chip>
          ) : null}
          {parsed!.priority > 0 ? (
            <Chip className="bg-surface-muted ring-border">
              <Flag className={cn("size-3 fill-current", PRIORITY_META[parsed!.priority as Priority].className)} />
              {PRIORITY_META[parsed!.priority as Priority].label}
            </Chip>
          ) : null}
          {parsed!.projectName ? (
            <Chip className="bg-surface-muted text-muted-foreground ring-border">
              <Hash className="size-3" />
              {parsed!.projectName}
            </Chip>
          ) : null}
          {parsed!.tagNames.map((tag) => (
            <Chip key={tag} className="bg-surface-muted text-muted-foreground ring-border">
              <TagIcon className="size-3" />
              {tag}
            </Chip>
          ))}
        </div>
      ) : null}

      <p id="quick-add-hint" className="sr-only">
        Type a task. Use hash for a project, at sign for a tag, exclamation mark p1 to p4 for
        priority, and plain words like tomorrow at 5pm or every weekday for scheduling.
      </p>
    </form>
  );
}

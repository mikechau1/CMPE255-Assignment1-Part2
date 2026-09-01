"use client";

import { RotateCcw, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { emptyTrash, purgeTask, restoreTask } from "@/app/actions/tasks";
import { EmptyState } from "@/components/task/empty-state";
import { Button } from "@/components/ui";
import { formatDueDate } from "@/lib/domain/dates";
import type { TaskDTO } from "@/lib/queries";

/**
 * Deleted tasks are kept rather than destroyed, so an accidental delete is
 * always recoverable — the toast's Undo is the fast path, this is the slow one.
 */
export function TrashView({ tasks }: { tasks: TaskDTO[] }) {
  const router = useRouter();
  const [pending, startTransition] = React.useTransition();

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 lg:py-10">
      <header className="mb-5 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Trash</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Deleted tasks stay here until you remove them for good.
          </p>
        </div>
        {tasks.length > 0 ? (
          <Button
            variant="ghost"
            size="sm"
            className="text-danger"
            disabled={pending}
            onClick={() =>
              startTransition(async () => {
                await emptyTrash();
                router.refresh();
                toast.success("Trash emptied");
              })
            }
          >
            <Trash2 className="size-4" />
            Empty trash
          </Button>
        ) : null}
      </header>

      {tasks.length === 0 ? (
        <EmptyState
          icon={Trash2}
          title="Trash is empty"
          description="Deleted tasks rest here until you empty it."
        />
      ) : (
        <ul className="space-y-0.5">
          {tasks.map((task) => (
            <li
              key={task.id}
              className="group/row flex items-center gap-3 rounded-xl px-2.5 py-2.5 hover:bg-surface-muted"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-muted-foreground line-through">{task.title}</p>
                {task.dueDate ? (
                  <p className="mt-0.5 text-xs text-subtle-foreground">
                    Was due {formatDueDate(task.dueDate, task.hasTime)}
                  </p>
                ) : null}
              </div>

              <Button
                size="sm"
                variant="ghost"
                disabled={pending}
                onClick={() =>
                  startTransition(async () => {
                    await restoreTask(task.id);
                    router.refresh();
                    toast.success("Task restored", { description: task.title });
                  })
                }
              >
                <RotateCcw className="size-4" />
                Restore
              </Button>
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label={`Delete ${task.title} permanently`}
                disabled={pending}
                className="text-danger"
                onClick={() =>
                  startTransition(async () => {
                    await purgeTask(task.id);
                    router.refresh();
                  })
                }
              >
                <Trash2 className="size-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

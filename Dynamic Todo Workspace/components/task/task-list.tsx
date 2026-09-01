"use client";

import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { restrictToParentElement, restrictToVerticalAxis } from "@dnd-kit/modifiers";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import * as React from "react";

import { useAppStore } from "@/components/app-store";
import { TaskRow } from "@/components/task/task-row";
import { formatDayHeading } from "@/lib/domain/dates";
import { groupByDay } from "@/lib/domain/filters";
import type { TaskDTO } from "@/lib/queries";

/**
 * The list itself: drag-and-drop ordering, optional day grouping, and roving
 * keyboard focus.
 *
 * Dragging is only offered when the list is in manual order and ungrouped —
 * dropping a row into a day group would silently change its due date, which is
 * not what the gesture promises.
 */
export function TaskList({
  tasks,
  groupByDate = false,
  activeId,
  emptyState,
}: {
  tasks: TaskDTO[];
  groupByDate?: boolean;
  activeId?: string | null;
  emptyState?: React.ReactNode;
}) {
  const store = useAppStore();
  const sortable = store.sort === "manual" && !groupByDate;

  const sensors = useSensors(
    // A small distance threshold keeps a click on the row from starting a drag.
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = React.useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (!over || active.id === over.id) return;

      const ids = tasks.map((task) => task.id);
      const from = ids.indexOf(String(active.id));
      const to = ids.indexOf(String(over.id));
      if (from === -1 || to === -1) return;

      const orderedIds = arrayMove(ids, from, to);
      store.move(String(active.id), orderedIds);
      store.announce(`Moved to position ${to + 1} of ${ids.length}`);
    },
    [store, tasks],
  );

  if (tasks.length === 0) return <>{emptyState}</>;

  if (groupByDate) {
    const groups = groupByDay(tasks);
    return (
      <div className="space-y-6">
        {groups.map((group) => (
          <section key={group.date?.toISOString() ?? "undated"}>
            <h3 className="mb-1 px-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {formatDayHeading(group.date)}
              <span className="ml-2 font-normal normal-case tracking-normal text-subtle-foreground">
                {group.tasks.length}
              </span>
            </h3>
            <ul className="space-y-0.5">
              {group.tasks.map((task) => (
                <TaskRow key={task.id} task={task} sortable={false} active={activeId === task.id} />
              ))}
            </ul>
          </section>
        ))}
      </div>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      modifiers={[restrictToVerticalAxis, restrictToParentElement]}
      onDragEnd={handleDragEnd}
    >
      <SortableContext items={tasks.map((task) => task.id)} strategy={verticalListSortingStrategy}>
        <ul className="space-y-0.5">
          {tasks.map((task) => (
            <TaskRow key={task.id} task={task} sortable={sortable} active={activeId === task.id} />
          ))}
        </ul>
      </SortableContext>
    </DndContext>
  );
}

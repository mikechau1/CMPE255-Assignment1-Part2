"use server";

import { getSubtasks } from "@/lib/queries";
import type { TaskDTO } from "@/lib/queries";

/**
 * Subtasks are loaded on demand rather than shipped with every list: only the
 * open detail panel needs them, and the row already carries its own n/m count.
 */
export async function loadSubtasks(parentId: string): Promise<TaskDTO[]> {
  return getSubtasks(parentId);
}

/**
 * Fractional indexing for manual ordering.
 *
 * Dropping a task between two neighbours only needs to write the dragged row:
 * its new position is the midpoint of the two positions around it. Repeated
 * midpoints eventually exhaust float precision, so `needsRebalance` reports
 * when a list should be renumbered with `rebalance`.
 */

export const POSITION_STEP = 1024;

/** Below this gap, another midpoint would start losing precision. */
export const MIN_GAP = 0.000001;

/**
 * Position for an item dropped between `prev` and `next`.
 * Pass null for either side to mean "start of list" / "end of list".
 */
export function computePosition(prev: number | null, next: number | null): number {
  if (prev === null && next === null) return POSITION_STEP;
  if (prev === null) return next! - POSITION_STEP;
  if (next === null) return prev + POSITION_STEP;
  return (prev + next) / 2;
}

/** True when the gap between neighbours is too small to split again. */
export function needsRebalance(prev: number | null, next: number | null): boolean {
  if (prev === null || next === null) return false;
  return Math.abs(next - prev) < MIN_GAP;
}

/** Evenly spaced positions for an ordered list of ids. */
export function rebalance(ids: string[]): { id: string; position: number }[] {
  return ids.map((id, index) => ({ id, position: (index + 1) * POSITION_STEP }));
}

/**
 * Given the ordered ids of a list and where an item was dropped, work out the
 * position to persist. `toIndex` is the index the item should occupy in the
 * list *with the item already removed from its old slot*.
 */
export function positionForDrop(
  orderedPositions: number[],
  toIndex: number,
): number {
  const prev = toIndex > 0 ? (orderedPositions[toIndex - 1] ?? null) : null;
  const next = toIndex < orderedPositions.length ? (orderedPositions[toIndex] ?? null) : null;
  return computePosition(prev, next);
}

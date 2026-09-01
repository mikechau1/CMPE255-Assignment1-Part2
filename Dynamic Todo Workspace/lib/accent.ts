import type { Accent } from "./domain/types";

/**
 * Accent classes are written out in full rather than composed at runtime.
 * Tailwind only ships the classes it can see in the source, so a template
 * like `bg-${color}-500` would silently produce an unstyled dot.
 */
interface AccentClasses {
  /** Solid dot / swatch. */
  dot: string;
  /** Tinted pill used by tag chips. */
  chip: string;
  /** Text-only tint. */
  text: string;
  /** Chart series colour. */
  hex: string;
  label: string;
}

export const ACCENT_CLASSES: Record<Accent, AccentClasses> = {
  violet: {
    dot: "bg-violet-500",
    chip: "bg-violet-500/12 text-violet-700 dark:text-violet-300 ring-violet-500/25",
    text: "text-violet-600 dark:text-violet-400",
    hex: "#8b5cf6",
    label: "Violet",
  },
  sky: {
    dot: "bg-sky-500",
    chip: "bg-sky-500/12 text-sky-700 dark:text-sky-300 ring-sky-500/25",
    text: "text-sky-600 dark:text-sky-400",
    hex: "#0ea5e9",
    label: "Sky",
  },
  emerald: {
    dot: "bg-emerald-500",
    chip: "bg-emerald-500/12 text-emerald-700 dark:text-emerald-300 ring-emerald-500/25",
    text: "text-emerald-600 dark:text-emerald-400",
    hex: "#10b981",
    label: "Emerald",
  },
  amber: {
    dot: "bg-amber-500",
    chip: "bg-amber-500/12 text-amber-700 dark:text-amber-300 ring-amber-500/25",
    text: "text-amber-600 dark:text-amber-400",
    hex: "#f59e0b",
    label: "Amber",
  },
  rose: {
    dot: "bg-rose-500",
    chip: "bg-rose-500/12 text-rose-700 dark:text-rose-300 ring-rose-500/25",
    text: "text-rose-600 dark:text-rose-400",
    hex: "#f43f5e",
    label: "Rose",
  },
  cyan: {
    dot: "bg-cyan-500",
    chip: "bg-cyan-500/12 text-cyan-700 dark:text-cyan-300 ring-cyan-500/25",
    text: "text-cyan-600 dark:text-cyan-400",
    hex: "#06b6d4",
    label: "Cyan",
  },
  lime: {
    dot: "bg-lime-500",
    chip: "bg-lime-500/12 text-lime-700 dark:text-lime-300 ring-lime-500/25",
    text: "text-lime-600 dark:text-lime-400",
    hex: "#84cc16",
    label: "Lime",
  },
  fuchsia: {
    dot: "bg-fuchsia-500",
    chip: "bg-fuchsia-500/12 text-fuchsia-700 dark:text-fuchsia-300 ring-fuchsia-500/25",
    text: "text-fuchsia-600 dark:text-fuchsia-400",
    hex: "#d946ef",
    label: "Fuchsia",
  },
  slate: {
    dot: "bg-slate-400",
    chip: "bg-slate-500/12 text-slate-700 dark:text-slate-300 ring-slate-500/25",
    text: "text-slate-600 dark:text-slate-400",
    hex: "#94a3b8",
    label: "Slate",
  },
};

export function accentClasses(color: string): AccentClasses {
  return ACCENT_CLASSES[color as Accent] ?? ACCENT_CLASSES.slate;
}

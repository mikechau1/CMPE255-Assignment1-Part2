"use client";

import { AlertTriangle, CheckCircle2, Flame, ListTodo } from "lucide-react";
import { useTheme } from "next-themes";
import * as React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { accentClasses } from "@/lib/accent";
import type { ProjectBreakdown, TaskStats } from "@/lib/domain/stats";
import { cn } from "@/lib/utils";

/*
 * Series colours are validated against both chart surfaces (lightness band,
 * chroma floor, and >=3:1 contrast) rather than picked by eye. One series, so
 * the heading names it and no legend is needed.
 */
const SERIES_LIGHT = "#7c3aed";
const SERIES_DARK = "#8b5cf6";

export function StatsDashboard({
  stats,
  breakdown,
}: {
  stats: TaskStats;
  breakdown: ProjectBreakdown[];
}) {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const isDark = mounted && resolvedTheme === "dark";
  const series = isDark ? SERIES_DARK : SERIES_LIGHT;
  const axis = isDark ? "#9aa0ae" : "#6b7180";
  const grid = isDark ? "#3a3d47" : "#e8e8ee";

  const busiest = stats.daily.reduce((max, day) => Math.max(max, day.count), 0);

  return (
    <div className="space-y-6">
      <section aria-label="Summary" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          icon={<ListTodo className="size-4" />}
          label="Open"
          value={stats.open}
          hint={`${stats.dueToday} due today`}
        />
        <StatTile
          icon={<AlertTriangle className="size-4" />}
          label="Overdue"
          value={stats.overdue}
          hint={stats.overdue === 0 ? "All caught up" : "Needs attention"}
          tone={stats.overdue > 0 ? "danger" : undefined}
        />
        <StatTile
          icon={<CheckCircle2 className="size-4" />}
          label="Done this week"
          value={stats.completedThisWeek}
          hint={`${Math.round(stats.completionRate * 100)}% of all tasks`}
        />
        <StatTile
          icon={<Flame className="size-4" />}
          label="Streak"
          value={stats.streak}
          hint={stats.streak === 1 ? "day in a row" : "days in a row"}
        />
      </section>

      <section className="rounded-xl bg-surface p-4 ring-1 ring-border sm:p-5">
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold">Tasks completed, last 30 days</h2>
          <p className="text-xs text-muted-foreground">
            Busiest day: {busiest} {busiest === 1 ? "task" : "tasks"}
          </p>
        </div>

        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={stats.daily} margin={{ top: 4, right: 4, bottom: 0, left: -22 }}>
              <CartesianGrid stroke={grid} strokeDasharray="2 4" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: axis, fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: grid }}
                interval={6}
              />
              <YAxis
                allowDecimals={false}
                width={44}
                tick={{ fill: axis, fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <RechartsTooltip
                cursor={{ fill: isDark ? "#ffffff12" : "#00000008" }}
                content={<ChartTooltip />}
              />
              {/* 4px rounded data-end, anchored to the baseline. */}
              <Bar dataKey="count" fill={series} radius={[4, 4, 0, 0]} maxBarSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* The same numbers as a table, for screen readers and for print. */}
        <details className="mt-3">
          <summary className="cursor-pointer text-xs text-muted-foreground">
            View as a table
          </summary>
          <div className="scrollbar-thin mt-2 max-h-56 overflow-y-auto">
            <table className="w-full text-left text-xs">
              <caption className="sr-only">Tasks completed per day over the last 30 days</caption>
              <thead className="sticky top-0 bg-surface text-subtle-foreground">
                <tr>
                  <th scope="col" className="py-1 font-medium">Day</th>
                  <th scope="col" className="py-1 text-right font-medium">Completed</th>
                </tr>
              </thead>
              <tbody className="text-muted-foreground">
                {stats.daily.map((day) => (
                  <tr key={day.key} className="border-t border-border">
                    <td className="py-1">{day.label}</td>
                    <td className="py-1 text-right tabular-nums">{day.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>

      <section className="rounded-xl bg-surface p-4 ring-1 ring-border sm:p-5">
        <h2 className="mb-4 text-sm font-semibold">Progress by project</h2>

        {breakdown.length === 0 ? (
          <p className="text-sm text-muted-foreground">No tasks yet.</p>
        ) : (
          <ul className="space-y-3.5">
            {breakdown.map((project) => {
              const percent = project.total === 0 ? 0 : Math.round((project.completed / project.total) * 100);
              return (
                <li key={project.projectId}>
                  <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
                    <span className="inline-flex min-w-0 items-center gap-2">
                      <span className={cn("size-2 shrink-0 rounded-full", accentClasses(project.color).dot)} />
                      <span className="truncate">{project.name}</span>
                    </span>
                    <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                      {project.completed}/{project.total} · {percent}%
                    </span>
                  </div>
                  <div
                    className="h-2 overflow-hidden rounded-full bg-surface-muted"
                    role="meter"
                    aria-valuenow={percent}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${project.name} progress`}
                  >
                    <div
                      className="h-full rounded-full bg-accent transition-[width] duration-500"
                      style={{ width: `${percent}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: { label: string; count: number } }[];
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0]!.payload;

  return (
    <div className="rounded-lg bg-foreground px-2.5 py-1.5 text-xs text-background shadow-lg">
      <p className="font-medium">{point.label}</p>
      <p className="opacity-80">
        {point.count} {point.count === 1 ? "task" : "tasks"} completed
      </p>
    </div>
  );
}

function StatTile({
  icon,
  label,
  value,
  hint,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  hint: string;
  tone?: "danger";
}) {
  return (
    <div className="rounded-xl bg-surface p-4 ring-1 ring-border">
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <span className={cn(tone === "danger" && value > 0 ? "text-danger" : undefined)}>{icon}</span>
        {label}
      </div>
      <p
        className={cn(
          "mt-1.5 text-3xl font-semibold tabular-nums tracking-tight",
          tone === "danger" && value > 0 ? "text-danger" : "text-foreground",
        )}
      >
        {value}
      </p>
      <p className="mt-0.5 text-xs text-subtle-foreground">{hint}</p>
    </div>
  );
}

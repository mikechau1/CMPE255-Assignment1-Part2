import { StatsDashboard } from "@/components/stats/stats-dashboard";
import { computeProjectBreakdown, computeStats } from "@/lib/domain/stats";
import { getAllTasksForStats, getProjects } from "@/lib/queries";

export const metadata = { title: "Stats" };

export default async function StatsPage() {
  const [tasks, projects] = await Promise.all([getAllTasksForStats(), getProjects()]);

  const stats = computeStats(tasks, new Date());
  const breakdown = computeProjectBreakdown(tasks, projects);

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 lg:py-10">
      <header className="mb-5">
        <h1 className="text-2xl font-semibold tracking-tight">Stats</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          How much is moving, and what is falling behind.
        </p>
      </header>

      <StatsDashboard stats={stats} breakdown={breakdown} />
    </div>
  );
}

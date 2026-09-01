import { TaskView } from "@/components/task/task-view";

export const metadata = { title: "Upcoming" };

export default function UpcomingPage() {
  return (
    <TaskView
      view="upcoming"
      title="Upcoming"
      subtitle="The next seven days, grouped by day."
      groupByDate
    />
  );
}

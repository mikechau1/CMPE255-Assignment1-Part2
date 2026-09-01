import { format } from "date-fns";

import { TaskView } from "@/components/task/task-view";

export const metadata = { title: "Today" };

export default function TodayPage() {
  return (
    <TaskView
      view="today"
      title="Today"
      subtitle={`${format(new Date(), "EEEE, d MMMM")} — due today, plus anything overdue.`}
    />
  );
}

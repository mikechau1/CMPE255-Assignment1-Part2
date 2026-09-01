import { TaskView } from "@/components/task/task-view";

export const metadata = { title: "All tasks" };

export default function AllPage() {
  return <TaskView view="all" title="All tasks" subtitle="Every open task, in your manual order." />;
}

import { TaskView } from "@/components/task/task-view";

export const metadata = { title: "Completed" };

export default function CompletedPage() {
  return <TaskView view="completed" title="Completed" subtitle="Everything you have ticked off." />;
}

import { TrashView } from "@/components/task/trash-view";
import { getDeletedTasks } from "@/lib/queries";

export const metadata = { title: "Trash" };

export default async function TrashPage() {
  return <TrashView tasks={await getDeletedTasks()} />;
}

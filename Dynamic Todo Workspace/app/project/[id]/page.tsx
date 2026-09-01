import { notFound } from "next/navigation";

import { TaskView } from "@/components/task/task-view";
import { getProject } from "@/lib/queries";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const project = await getProject((await params).id);
  return { title: project?.name ?? "Project" };
}

export default async function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const project = await getProject((await params).id);
  if (!project) notFound();

  return (
    <TaskView
      view="all"
      projectId={project.id}
      title={project.emoji ? `${project.emoji}  ${project.name}` : project.name}
      subtitle={project.isInbox ? "Anything without a home lands here." : undefined}
    />
  );
}

"use client";

import {
  BarChart3,
  CalendarDays,
  CheckCircle2,
  Inbox,
  LayoutList,
  Plus,
  Sun,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as React from "react";

import { createProject } from "@/app/actions/projects";
import { useAppStore } from "@/components/app-store";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button, Input, Tooltip } from "@/components/ui";
import { accentClasses } from "@/lib/accent";
import { isDueTodayOrOverdue, isUpcoming } from "@/lib/domain/filters";
import { cn } from "@/lib/utils";

const VIEW_LINKS = [
  { href: "/today", label: "Today", icon: Sun },
  { href: "/upcoming", label: "Upcoming", icon: CalendarDays },
  { href: "/all", label: "All tasks", icon: LayoutList },
  { href: "/completed", label: "Completed", icon: CheckCircle2 },
] as const;

export function Sidebar({ trashCount }: { trashCount: number }) {
  const store = useAppStore();
  const pathname = usePathname();
  const router = useRouter();
  const [creating, setCreating] = React.useState(false);
  const [name, setName] = React.useState("");

  const now = new Date();
  const counts: Record<string, number> = {
    "/today": store.tasks.filter((task) => !task.completed && isDueTodayOrOverdue(task, now)).length,
    "/upcoming": store.tasks.filter((task) => !task.completed && isUpcoming(task, now)).length,
    "/all": store.tasks.filter((task) => !task.completed).length,
    "/completed": store.tasks.filter((task) => task.completed).length,
  };

  async function submitProject(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setName("");
    setCreating(false);
    await createProject({ name: trimmed });
    router.refresh();
  }

  return (
    <nav
      aria-label="Views and projects"
      className="scrollbar-thin flex h-full flex-col gap-6 overflow-y-auto px-3 py-4"
    >
      <div className="flex items-center justify-between px-2">
        <Link href="/today" className="flex items-center gap-2 rounded-lg">
          <span className="grid size-7 place-items-center rounded-lg bg-accent text-accent-foreground">
            <CheckCircle2 className="size-4" />
          </span>
          <span className="text-sm font-semibold tracking-tight">Momentum</span>
        </Link>
        <ThemeToggle />
      </div>

      <ul className="space-y-0.5">
        {VIEW_LINKS.map((link) => (
          <li key={link.href}>
            <SidebarLink
              href={link.href}
              active={pathname === link.href}
              icon={<link.icon className="size-4" />}
              count={counts[link.href]}
              overdueTint={link.href === "/today"}
            >
              {link.label}
            </SidebarLink>
          </li>
        ))}
      </ul>

      <div>
        <div className="mb-1 flex items-center justify-between px-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-subtle-foreground">
            Projects
          </h2>
          <Tooltip content="New project">
            <button
              type="button"
              onClick={() => setCreating((value) => !value)}
              aria-label="New project"
              aria-expanded={creating}
              className="grid size-6 place-items-center rounded-md text-muted-foreground hover:bg-surface-muted"
            >
              <Plus className="size-3.5" />
            </button>
          </Tooltip>
        </div>

        {creating ? (
          <form onSubmit={submitProject} className="mb-1.5 px-1">
            <Input
              autoFocus
              value={name}
              onChange={(event) => setName(event.target.value)}
              onBlur={() => !name.trim() && setCreating(false)}
              onKeyDown={(event) => event.key === "Escape" && setCreating(false)}
              placeholder="Project name"
              aria-label="Project name"
              className="h-8 text-[13px]"
            />
          </form>
        ) : null}

        <ul className="space-y-0.5">
          {store.projects.map((project) => (
            <li key={project.id}>
              <SidebarLink
                href={`/project/${project.id}`}
                active={pathname === `/project/${project.id}`}
                count={project.openCount}
                icon={
                  project.isInbox ? (
                    <Inbox className="size-4" />
                  ) : project.emoji ? (
                    <span className="text-[13px] leading-none">{project.emoji}</span>
                  ) : (
                    <span className={cn("size-2 rounded-full", accentClasses(project.color).dot)} />
                  )
                }
              >
                {project.name}
              </SidebarLink>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-auto space-y-0.5">
        <SidebarLink href="/stats" active={pathname === "/stats"} icon={<BarChart3 className="size-4" />}>
          Stats
        </SidebarLink>
        <SidebarLink
          href="/trash"
          active={pathname === "/trash"}
          icon={<Trash2 className="size-4" />}
          count={trashCount}
        >
          Trash
        </SidebarLink>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start px-2.5 font-normal"
          onClick={() => store.setShortcutsOpen(true)}
        >
          Keyboard shortcuts
          <kbd className="ml-auto text-xs text-subtle-foreground">?</kbd>
        </Button>
      </div>
    </nav>
  );
}

function SidebarLink({
  href,
  active,
  icon,
  count,
  overdueTint,
  children,
}: {
  href: string;
  active: boolean;
  icon: React.ReactNode;
  count?: number;
  overdueTint?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm transition-colors",
        active
          ? "bg-accent-soft font-medium text-accent"
          : "text-muted-foreground hover:bg-surface-muted hover:text-foreground",
      )}
    >
      <span className="grid w-4 shrink-0 place-items-center">{icon}</span>
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {count ? (
        <span
          className={cn(
            "text-xs tabular-nums",
            overdueTint && !active ? "text-muted-foreground" : "text-subtle-foreground",
          )}
        >
          {count}
        </span>
      ) : null}
    </Link>
  );
}

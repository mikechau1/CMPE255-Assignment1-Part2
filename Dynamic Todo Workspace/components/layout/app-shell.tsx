"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { BarChart3, CalendarDays, LayoutList, Menu, Sun, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { useAppStore } from "@/components/app-store";
import { CommandPalette } from "@/components/layout/command-palette";
import { ShortcutsDialog } from "@/components/layout/shortcuts-dialog";
import { Sidebar } from "@/components/layout/sidebar";
import { BulkActionBar } from "@/components/task/bulk-action-bar";
import { TaskDetailPanel } from "@/components/task/task-detail-panel";
import { Button } from "@/components/ui";
import { useHotkeys } from "@/lib/hooks/use-hotkeys";
import { cn } from "@/lib/utils";

const MOBILE_LINKS = [
  { href: "/today", label: "Today", icon: Sun },
  { href: "/upcoming", label: "Upcoming", icon: CalendarDays },
  { href: "/all", label: "All", icon: LayoutList },
  { href: "/stats", label: "Stats", icon: BarChart3 },
] as const;

/**
 * The application frame: navigation, the global shortcuts, and the surfaces
 * that can appear over any view (palette, detail panel, bulk bar, toasts).
 */
export function AppShell({
  trashCount,
  children,
}: {
  trashCount: number;
  children: React.ReactNode;
}) {
  const store = useAppStore();
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  React.useEffect(() => setDrawerOpen(false), [pathname]);

  useHotkeys({
    "mod+k": () => store.setPaletteOpen(!store.paletteOpen),
    n: () => store.focusQuickAdd(),
    "/": () => store.focusSearch(),
    "?": () => store.setShortcutsOpen(true),
    Escape: () => {
      // Unwind one layer at a time, outermost surface first.
      if (store.paletteOpen) store.setPaletteOpen(false);
      else if (store.shortcutsOpen) store.setShortcutsOpen(false);
      else if (store.selectedTaskId) store.setSelectedTaskId(null);
      else if (store.checkedIds.length) store.clearChecked();
    },
  });

  return (
    <div className="flex min-h-dvh flex-col bg-background md:flex-row">
      <a
        href="#main"
        className="sr-only-focusable absolute left-3 top-3 z-50 rounded-lg bg-accent px-3 py-2 text-sm text-accent-foreground"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 border-r border-border bg-surface-muted/40 md:block">
        <Sidebar trashCount={trashCount} />
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center gap-2 border-b border-border bg-background/85 px-3 py-2 backdrop-blur md:hidden">
        <Button
          size="icon"
          variant="ghost"
          aria-label="Open navigation"
          onClick={() => setDrawerOpen(true)}
        >
          <Menu className="size-5" />
        </Button>
        <span className="text-sm font-semibold">Momentum</span>
      </header>

      <DialogPrimitive.Root open={drawerOpen} onOpenChange={setDrawerOpen}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-40 animate-fade-in bg-[var(--overlay)] md:hidden" />
          <DialogPrimitive.Content
            aria-describedby={undefined}
            className="fixed inset-y-0 left-0 z-50 w-72 animate-slide-up border-r border-border bg-surface shadow-2xl focus:outline-none md:hidden"
          >
            <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
            <DialogPrimitive.Close asChild>
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label="Close navigation"
                className="absolute right-2 top-3 z-10"
              >
                <X className="size-4" />
              </Button>
            </DialogPrimitive.Close>
            <Sidebar trashCount={trashCount} />
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>

      <main id="main" className="min-w-0 flex-1 pb-20 md:pb-0">
        {children}
      </main>

      {/* Mobile bottom navigation */}
      <nav
        aria-label="Primary"
        className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-background/95 backdrop-blur md:hidden"
      >
        {MOBILE_LINKS.map((link) => {
          const active = pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-[11px]",
                active ? "text-accent" : "text-muted-foreground",
              )}
            >
              <link.icon className="size-5" />
              {link.label}
            </Link>
          );
        })}
      </nav>

      <CommandPalette />
      <ShortcutsDialog />
      <TaskDetailPanel />
      <BulkActionBar />

      {/*
        One polite live region for the whole app. Optimistic updates change the
        DOM without moving focus, so without this a screen-reader user gets no
        confirmation that anything happened.
      */}
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {store.announcement}
      </div>
    </div>
  );
}

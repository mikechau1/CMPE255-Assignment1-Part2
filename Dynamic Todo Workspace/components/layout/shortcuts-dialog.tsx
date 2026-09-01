"use client";

import { useAppStore } from "@/components/app-store";
import { Dialog, DialogContent, DialogDescription, DialogTitle, Kbd } from "@/components/ui";
import { useIsMac } from "@/lib/hooks/use-hotkeys";

const GROUPS: { title: string; items: { keys: string[]; label: string }[] }[] = [
  {
    title: "General",
    items: [
      { keys: ["mod", "K"], label: "Open the command palette" },
      { keys: ["n"], label: "Add a task" },
      { keys: ["/"], label: "Search" },
      { keys: ["?"], label: "Show this list" },
      { keys: ["Esc"], label: "Close, clear, or deselect" },
    ],
  },
  {
    title: "Navigating the list",
    items: [
      { keys: ["j"], label: "Move down" },
      { keys: ["k"], label: "Move up" },
      { keys: ["Enter"], label: "Open task details" },
      { keys: ["Space"], label: "Complete or reopen" },
      { keys: ["x"], label: "Select for bulk actions" },
      { keys: ["e"], label: "Edit details" },
      { keys: ["#"], label: "Delete" },
    ],
  },
  {
    title: "Setting priority",
    items: [
      { keys: ["1"], label: "Urgent" },
      { keys: ["2"], label: "High" },
      { keys: ["3"], label: "Medium" },
      { keys: ["4"], label: "None" },
    ],
  },
];

export function ShortcutsDialog() {
  const store = useAppStore();
  const isMac = useIsMac();

  return (
    <Dialog open={store.shortcutsOpen} onOpenChange={store.setShortcutsOpen}>
      <DialogContent className="max-w-lg">
        <DialogTitle className="text-base font-semibold">Keyboard shortcuts</DialogTitle>
        <DialogDescription className="mt-1 text-sm text-muted-foreground">
          Every action here is reachable without a mouse.
        </DialogDescription>

        <div className="mt-4 grid gap-5 sm:grid-cols-2">
          {GROUPS.map((group) => (
            <section key={group.title}>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-subtle-foreground">
                {group.title}
              </h3>
              <ul className="space-y-1.5">
                {group.items.map((item) => (
                  <li key={item.label} className="flex items-center justify-between gap-3 text-sm">
                    <span className="text-muted-foreground">{item.label}</span>
                    <span className="flex shrink-0 gap-1">
                      {item.keys.map((key) => (
                        <Kbd key={key}>{key === "mod" ? (isMac ? "⌘" : "Ctrl") : key}</Kbd>
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

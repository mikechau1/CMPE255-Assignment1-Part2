"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import * as React from "react";

import { Button, Tooltip } from "@/components/ui";

/**
 * Theme switch.
 *
 * Renders a neutral placeholder until mounted: the server cannot know the
 * stored preference, and swapping the icon after hydration is what causes the
 * flicker people notice.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => setMounted(true), []);

  const isDark = resolvedTheme === "dark";

  return (
    <Tooltip content={isDark ? "Light mode" : "Dark mode"}>
      <Button
        size="icon-sm"
        variant="ghost"
        aria-label={mounted ? (isDark ? "Switch to light mode" : "Switch to dark mode") : "Toggle theme"}
        onClick={() => setTheme(isDark ? "light" : "dark")}
      >
        {mounted ? (
          isDark ? (
            <Moon className="size-4" />
          ) : (
            <Sun className="size-4" />
          )
        ) : (
          <span className="size-4" />
        )}
      </Button>
    </Tooltip>
  );
}

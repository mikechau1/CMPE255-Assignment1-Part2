"use client";

import { ThemeProvider } from "next-themes";
import * as React from "react";
import { Toaster } from "sonner";

import { TooltipProvider } from "@/components/ui";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <TooltipProvider delayDuration={400} skipDelayDuration={200}>
        {children}
        <Toaster
          position="bottom-center"
          closeButton
          // Undo needs long enough to notice the toast and reach for it.
          duration={6000}
          toastOptions={{
            classNames: {
              toast:
                "!bg-surface !text-foreground !border !border-border !rounded-xl !shadow-xl",
              description: "!text-muted-foreground",
              actionButton: "!bg-accent !text-accent-foreground !rounded-lg",
              closeButton: "!bg-surface !border-border !text-muted-foreground",
            },
          }}
        />
      </TooltipProvider>
    </ThemeProvider>
  );
}

"use client";

import * as React from "react";

import { Button } from "@/components/ui";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  React.useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex max-w-md flex-col items-center px-4 py-24 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">Something went wrong</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        The view failed to load. Your tasks are safe — nothing was lost.
      </p>
      <Button variant="primary" className="mt-5" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}

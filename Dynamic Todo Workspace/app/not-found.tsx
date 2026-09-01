import Link from "next/link";

import { Button } from "@/components/ui";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center px-4 py-24 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">Not found</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        That project or page does not exist — it may have been deleted.
      </p>
      <Button asChild variant="primary" className="mt-5">
        <Link href="/today">Back to Today</Link>
      </Button>
    </div>
  );
}

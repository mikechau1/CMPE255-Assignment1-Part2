import { Skeleton } from "@/components/ui";

/** Shown while a route segment streams in, sized to match the real list. */
export default function Loading() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 lg:py-10">
      <Skeleton className="h-8 w-40" />
      <Skeleton className="mt-2 h-4 w-64" />
      <Skeleton className="mt-5 h-11 w-full rounded-xl" />
      <Skeleton className="mt-4 h-9 w-full rounded-lg" />
      <div className="mt-4 space-y-2">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="flex items-start gap-3 px-2.5 py-2.5">
            <Skeleton className="size-[18px] rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4" style={{ width: `${70 - index * 6}%` }} />
              <Skeleton className="h-3 w-28" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

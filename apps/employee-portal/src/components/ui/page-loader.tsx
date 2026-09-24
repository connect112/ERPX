import { Loader2 } from "lucide-react";

/**
 * Full-height centered spinner used as the `Suspense` fallback while a
 * lazily-loaded route chunk is being fetched. Kept intentionally minimal so
 * it renders instantly (no data, no layout shift) between route navigations.
 */
export function PageLoader() {
  return (
    <div className="flex h-full w-full items-center justify-center py-24" role="status" aria-label="Loading">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}

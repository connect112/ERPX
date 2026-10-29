import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { useDuplicates } from "@/features/storage-manager/api/storage-hooks";
import { StatusBadge } from "@/features/storage-manager/components/status-badge";
import { formatBytes } from "@/features/storage-manager/lib/format";

/** Groups of identical files. Only copies with no record pointing at them can be deleted, from the Files tab. */
export function DuplicatesPanel({ active }: { active: boolean }) {
  const { data, isLoading, isError } = useDuplicates(active);

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (isError) return <p className="text-sm text-destructive">Duplicates could not be checked.</p>;
  if (!data || data.length === 0) return <p className="py-10 text-center text-sm text-muted-foreground">No identical files found.</p>;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Files with identical content. A copy that a record uses is never offered for deletion: only copies nothing points at can be removed.
      </p>
      {data.map((group) => (
        <Card key={group.fingerprint}>
          <CardContent className="space-y-2 p-4">
            <p className="text-sm font-medium">
              {group.count} copies of {formatBytes(group.size_bytes)} · {formatBytes(group.wasted_bytes)} duplicated
            </p>
            <ul className="space-y-1 text-sm">
              {group.files.map((file) => (
                <li key={file.id} className="flex flex-wrap items-center justify-between gap-2">
                  <span className="break-all">
                    {file.name} <span className="text-muted-foreground">· {file.source_label}</span>
                  </span>
                  <StatusBadge status={file.status} />
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

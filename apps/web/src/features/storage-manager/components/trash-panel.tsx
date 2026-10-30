import { RotateCcw } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage, usePurge, useRestore, useTrash } from "@/features/storage-manager/api/storage-hooks";
import { formatBytes, formatDate } from "@/features/storage-manager/lib/format";
import { purgeConfirmText } from "@/features/storage-manager/lib/rules";

/**
 * Files that were moved aside. Restore puts one back where it was. Permanent removal is a separate, typed, manual step
 * that the server refuses until a file has been here for the minimum period; nothing empties Trash by itself.
 */
export function TrashPanel({ canDelete }: { canDelete: boolean }) {
  const { data, isLoading, isError } = useTrash();
  const restore = useRestore();
  const purge = usePurge();
  const [purgeIds, setPurgeIds] = useState<string[]>([]);
  const [purging, setPurging] = useState(false);
  const [typed, setTyped] = useState("");

  const purgeable = (data?.items ?? []).filter((item) => item.can_purge);
  const confirmText = purgeConfirmText(purgeIds.length);

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Deleted files stay here for at least {data?.min_days ?? 30} days and can be restored. {data && `${data.total} items, ${formatBytes(data.total_bytes)}.`}
      </p>

      {restore.isError && <p className="text-sm text-destructive">{errorMessage(restore.error, "The file was not restored.")}</p>}

      {canDelete && purgeable.length > 0 && (
        <div className="flex items-center justify-between rounded-md border bg-muted/50 px-4 py-2 text-sm">
          <span>{purgeable.length} item(s) are past the minimum period and can be permanently removed.</span>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => {
              setPurgeIds(purgeable.map((item) => item.id));
              setTyped("");
              purge.reset();
              setPurging(true);
            }}
          >
            Permanently delete…
          </Button>
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          {isLoading && <Skeleton className="m-6 h-24" />}
          {isError && <p className="p-8 text-center text-sm text-destructive">Trash could not be loaded.</p>}
          {data && data.items.length === 0 && <p className="py-10 text-center text-sm text-muted-foreground">Trash is empty.</p>}
          {data && data.items.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>File</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Deleted</TableHead>
                  <TableHead>By</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Can be removed after</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="max-w-xs break-all font-medium">
                      {item.filename}
                      <div className="text-xs font-normal text-muted-foreground">{item.original_key}</div>
                    </TableCell>
                    <TableCell>{formatBytes(item.size_bytes)}</TableCell>
                    <TableCell>{formatDate(item.deleted_at)}</TableCell>
                    <TableCell>{item.deleted_by ?? "—"}</TableCell>
                    <TableCell className="max-w-xs">{item.reason}</TableCell>
                    <TableCell>{formatDate(item.purge_allowed_at)}</TableCell>
                    <TableCell>
                      {canDelete && (
                        <Button variant="outline" size="sm" disabled={restore.isPending} onClick={() => restore.mutate(item.id)}>
                          <RotateCcw className="h-4 w-4" /> Restore
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={purging} onOpenChange={setPurging}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Permanently delete {purgeIds.length} item(s)?</DialogTitle>
            <DialogDescription>This cannot be undone. The files will be gone for good.</DialogDescription>
          </DialogHeader>
          <div className="space-y-1">
            <label htmlFor="purge-confirm" className="text-sm font-medium">
              Type <code className="rounded bg-muted px-1">{confirmText}</code> to confirm
            </label>
            <Input id="purge-confirm" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
          </div>
          {purge.isError && <p className="text-sm text-destructive">{errorMessage(purge.error, "Nothing was removed.")}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setPurging(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={typed.trim() !== confirmText || purge.isPending}
              onClick={() => purge.mutate({ ids: purgeIds, confirm_text: typed.trim() }, { onSuccess: () => setPurging(false) })}
            >
              {purge.isPending ? "Removing…" : "Delete permanently"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage, useDeleteFiles, useDeletionPreview } from "@/features/storage-manager/api/storage-hooks";
import { formatBytes, VERDICT_LABELS } from "@/features/storage-manager/lib/format";
import { isDeleteReady } from "@/features/storage-manager/lib/rules";

interface Props {
  ids: string[];
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}

/**
 * Review, then confirm. Nothing is sent until the reason is written and the confirmation text is typed exactly, and
 * the server checks every file again before moving any of them.
 */
export function DeleteDialog({ ids, open, onClose, onDone }: Props) {
  const preview = useDeletionPreview();
  const remove = useDeleteFiles();
  const [reason, setReason] = useState("");
  const [typed, setTyped] = useState("");

  const { mutate: loadPreview, reset: resetPreview } = preview;
  const { reset: resetRemove } = remove;
  useEffect(() => {
    if (open && ids.length > 0) {
      setReason("");
      setTyped("");
      resetRemove();
      loadPreview(ids);
    } else {
      resetPreview();
    }
  }, [open, ids, loadPreview, resetPreview, resetRemove]);

  const data = preview.data;
  const ready = data !== undefined && isDeleteReady({ blockedCount: data.blocked_count, reason, typed, confirmText: data.confirm_text });

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Move {ids.length} {ids.length === 1 ? "file" : "files"} to Trash</DialogTitle>
          <DialogDescription>
            Files go to Trash, not away. They can be restored, and nothing is permanently deleted for at least 30 days.
          </DialogDescription>
        </DialogHeader>

        {preview.isPending && <Skeleton className="h-24 w-full" />}
        {preview.isError && <p className="text-sm text-destructive">{errorMessage(preview.error, "Could not check these files.")}</p>}

        {data && (
          <div className="space-y-3">
            <p className="text-sm">
              <strong>{data.eligible_count}</strong> can be moved ({formatBytes(data.total_bytes)} recovered).{" "}
              {data.blocked_count > 0 && (
                <span className="text-destructive">
                  {data.blocked_count} cannot be, so nothing will be moved until you deselect them.
                </span>
              )}
            </p>
            <ul className="max-h-56 space-y-2 overflow-auto rounded-md border p-3 text-sm">
              {data.items.map((analysis) => (
                <li key={analysis.item.id} className="space-y-0.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="break-all font-medium">{analysis.item.name}</span>
                    <span className={analysis.can_delete ? "text-emerald-600" : "text-destructive"}>
                      {VERDICT_LABELS[analysis.verdict] ?? analysis.verdict}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {formatBytes(analysis.item.size_bytes)} · {analysis.item.location}
                  </div>
                  {analysis.evidence.map((evidence, index) => (
                    <div key={index} className="text-xs text-muted-foreground">
                      {evidence.text}
                    </div>
                  ))}
                </li>
              ))}
            </ul>

            <div className="space-y-1">
              <label htmlFor="delete-reason" className="text-sm font-medium">
                Reason (kept in the deletion log)
              </label>
              <Textarea id="delete-reason" value={reason} onChange={(e) => setReason(e.target.value)} rows={2} />
            </div>
            <div className="space-y-1">
              <label htmlFor="delete-confirm" className="text-sm font-medium">
                Type <code className="rounded bg-muted px-1">{data.confirm_text}</code> to confirm
              </label>
              <Input id="delete-confirm" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
            </div>
          </div>
        )}

        {remove.isError && <p className="text-sm text-destructive">{errorMessage(remove.error, "The files were not moved.")}</p>}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={!ready || remove.isPending}
            onClick={() =>
              data &&
              remove.mutate(
                { ids, reason: reason.trim(), confirm_text: typed.trim() },
                {
                  onSuccess: () => {
                    onDone();
                    onClose();
                  },
                }
              )
            }
          >
            {remove.isPending ? "Moving…" : "Move to Trash"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

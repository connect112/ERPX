import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

interface Props {
  name: string;
  /** The ERPX emails that currently use this template. Deleting is refused while there are any. */
  usedBy: string[];
  isSystem: boolean;
  /** The server's own reason, when the library says it cannot be deleted. */
  blockedReason?: string | null;
  pending?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onClose: () => void;
  /** Take the person to "Use for" to choose another template first. */
  onReassign?: () => void;
}

/** Asks before a template is deleted, names it, and explains (rather than just refusing) when it cannot be deleted. */
export function DeleteTemplateDialog({ name, usedBy, isSystem, blockedReason, pending, error, onConfirm, onClose, onReassign }: Props) {
  const blocked = isSystem || usedBy.length > 0;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{blocked ? "This template cannot be deleted" : "Delete this template?"}</DialogTitle>
          <DialogDescription>
            <strong className="break-words text-foreground">{name}</strong>
          </DialogDescription>
        </DialogHeader>
        {isSystem ? (
          <p className="text-sm">{blockedReason ?? "This is a protected system template and cannot be deleted."}</p>
        ) : usedBy.length > 0 ? (
          <div className="space-y-2 text-sm">
            <p>It is currently used for these ERPX emails:</p>
            <ul className="list-disc pl-5">
              {usedBy.map((u) => (
                <li key={u}>{u}</li>
              ))}
            </ul>
            <p className="text-muted-foreground">Choose another template for them (or switch them back to the built-in wording) under "Use for", then delete this one. Otherwise those emails would quietly change.</p>
          </div>
        ) : (
          <div className="space-y-2 text-sm">
            <p>It will be removed from your library. You can bring it back from <strong>Recently deleted</strong>.</p>
            <p className="text-muted-foreground">Emails already sent, their history and the audit trail are not affected.</p>
          </div>
        )}
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={onClose}>{blocked ? "Close" : "Cancel"}</Button>
          {!blocked && (
            <Button variant="destructive" disabled={pending} onClick={onConfirm}>
              {pending ? "Deleting..." : "Delete template"}
            </Button>
          )}
          {!isSystem && usedBy.length > 0 && onReassign && <Button onClick={onReassign}>Go to "Use for"</Button>}
        </div>
      </DialogContent>
    </Dialog>
  );
}

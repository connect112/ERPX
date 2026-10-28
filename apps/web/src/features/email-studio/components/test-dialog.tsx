import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { type DraftPayload, type SourceType, studioApi } from "@/features/email-studio/api/studio-api";
import { errorMessage } from "@/features/institutions/lib/format";
import { useAuthStore } from "@/store/auth-store";

/** Sends what is on screen to one address, marked as a test, with sample values. Works before a template is saved. */
export function TestDialog({
  sourceType,
  templateId,
  getDraft,
  erpxKey,
  onClose,
}: {
  sourceType: SourceType;
  templateId?: string;
  getDraft: () => Promise<DraftPayload>;
  erpxKey: string | null;
  onClose: () => void;
}) {
  const [to, setTo] = useState(useAuthStore.getState().user?.email ?? "");
  const send = useMutation({ mutationFn: async () => studioApi.test(sourceType, await getDraft(), { type: "sample", key: erpxKey }, to.trim(), templateId) });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Send a test email</DialogTitle>
          <DialogDescription>Sends what is on screen, with sample values and safe sample links, to one address. It is marked as a test and starts nothing in ERPX.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="es-test-to">Send to</Label>
            <Input id="es-test-to" type="email" value={to} onChange={(e) => setTo(e.target.value)} />
          </div>
          {send.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(send.error, "Could not send the test.")}</p>}
          {send.data && <p role="status" className={`text-sm ${send.data.sent ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"}`}>{send.data.message}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Close</Button>
            <Button disabled={!to.trim() || send.isPending} onClick={() => send.mutate()}>{send.isPending ? "Sending..." : "Send test"}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

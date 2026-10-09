import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ReplyRecord, ReplyStatus, Triage } from "@/features/social-media/api/social-media-api";
import { CATEGORY_LABEL, REPLY_STATUS_LABEL, REPLY_STATUS_VARIANT } from "@/features/social-media/lib/inbox-labels";
import { useReconcileReply, useResolveReply } from "@/features/social-media/api/social-media-hooks";
import { errorMessage } from "@/features/social-media/lib/format";

export function TriageBadges({ triage }: { triage: Triage }) {
  return (
    <>
      <Badge variant={triage.category === "complaint" ? "destructive" : triage.category === "enquiry" ? "info" : "secondary"}>{CATEGORY_LABEL[triage.category]}</Badge>
      {triage.priority === "high" && <Badge variant="warning">High priority</Badge>}
      {triage.needs_care && <Badge variant="outline">Handle personally</Badge>}
    </>
  );
}

export function ReplyStatusBadge({ status }: { status: ReplyStatus }) {
  return <Badge variant={REPLY_STATUS_VARIANT[status]}>{REPLY_STATUS_LABEL[status]}</Badge>;
}

/**
 * A reply whose outcome is not known. It is never sent again automatically (it may have gone out). A person can ask Instagram
 * whether it is there, or look themselves and record what they saw.
 */
export function UnclearReply({ reply, onSettled }: { reply: ReplyRecord; onSettled?: (reply: ReplyRecord) => void }) {
  const reconcile = useReconcileReply();
  const resolve = useResolveReply();
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const busy = reconcile.isPending || resolve.isPending;

  function check() {
    setError(null);
    reconcile.mutate(reply.id, {
      onSuccess: (r) => {
        setNote(r.note);
        onSettled?.(r.reply);
      },
      onError: (e) => setError(errorMessage(e, "Couldn't check.")),
    });
  }

  function record(sent: boolean) {
    setError(null);
    resolve.mutate(
      { id: reply.id, sent },
      {
        onSuccess: (r) => {
          setConfirming(false);
          onSettled?.(r);
        },
        onError: (e) => setError(errorMessage(e, "Couldn't record that.")),
      },
    );
  }

  return (
    <div role="alert" className="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
      <p className="font-medium">It isn&apos;t known whether this was sent</p>
      <p>{reply.error ?? "Instagram didn't give a clear answer."}</p>
      {note && <p className="text-xs">{note}</p>}
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={check} disabled={busy}>
          {reconcile.isPending ? "Checking…" : "Check with Instagram"}
        </Button>
        {!confirming ? (
          <Button size="sm" variant="outline" onClick={() => setConfirming(true)} disabled={busy}>
            I looked myself
          </Button>
        ) : (
          <>
            <Button size="sm" variant="outline" onClick={() => record(true)} disabled={busy}>
              It is there
            </Button>
            <Button size="sm" variant="outline" onClick={() => record(false)} disabled={busy}>
              It is not there
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

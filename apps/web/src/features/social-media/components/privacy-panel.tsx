import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { ErasureResult, RetentionCounts } from "@/features/social-media/api/social-media-api";
import { useErasePerson, useRetentionStatus, useRunRetention } from "@/features/social-media/api/social-media-hooks";
import { errorMessage, formatInZone } from "@/features/social-media/lib/format";

const LABEL: Record<string, string> = {
  messages: "messages",
  conversations: "conversations",
  comments: "comments",
  reply_texts: "reply texts",
  posts_read: "posts read from Instagram",
  notifications: "Instagram notifications",
};

function describe(counts: Record<string, number | string>): string {
  const parts = Object.entries(LABEL)
    .map(([key, label]) => [Number(counts[key] ?? 0), label] as const)
    .filter(([n]) => n > 0)
    .map(([n, label]) => `${n} ${label}`);
  return parts.length ? parts.join(", ") : "nothing";
}

/** What the retention period removes (and keeps), and erasing one person's data on request. */
export function PrivacyPanel() {
  const me = useMyRoles();
  const permissions = me.data?.effective_permissions ?? [];
  const canManage = (me.data?.is_superuser ?? false) || permissions.includes("social_media.manage");
  const canErase = canManage && ((me.data?.is_superuser ?? false) || permissions.includes("social_media.inbox"));
  const status = useRetentionStatus(canManage);
  const run = useRunRetention();
  const erase = useErasePerson();
  const [handle, setHandle] = useState("");
  const [found, setFound] = useState<{ handle: string; result: ErasureResult } | null>(null);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  if (!canManage) return null;
  const pending: RetentionCounts | undefined = status.data?.past_the_period;
  const anyPending = pending ? Object.entries(LABEL).some(([key]) => Number((pending as unknown as Record<string, number>)[key]) > 0) : false;

  function removeNow() {
    setNotice(null);
    run.mutate(true, {
      onSuccess: (r) => setNotice({ ok: true, text: `Removed ${describe(r.removed ?? {})}.` }),
      onError: (e) => setNotice({ ok: false, text: errorMessage(e, "Couldn't remove it.") }),
    });
  }

  function count() {
    setNotice(null);
    setFound(null);
    erase.mutate({ handle: handle.trim(), confirm: false }, { onSuccess: (r) => setFound({ handle: handle.trim(), result: r }), onError: (e) => setNotice({ ok: false, text: errorMessage(e, "Couldn't look that up.") }) });
  }

  function confirmErase() {
    if (!found) return;
    erase.mutate(
      { handle: found.handle, confirm: true },
      {
        onSuccess: (r) => {
          setFound(null);
          setHandle("");
          setNotice({ ok: true, text: `Erased ${r.comments} comment(s), ${r.conversations} conversation(s) with ${r.messages} message(s), and the text of ${r.reply_texts} reply(ies).` });
        },
        onError: (e) => setNotice({ ok: false, text: errorMessage(e, "Couldn't erase it.") }),
      },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Privacy and retention</CardTitle>
        <CardDescription>Comments, messages and the text of replies are removed once they are older than the retention period (set under Settings, further down this page). This runs every day.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6 text-sm">
        {status.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : status.data ? (
          <div className="space-y-2">
            <p>
              Retention period: <span className="font-medium">{status.data.retention_days} days</span>. Last daily run:{" "}
              {status.data.last_run_at ? `${formatInZone(status.data.last_run_at, "Asia/Kolkata")}${status.data.last_run_ok === false ? " (it failed)" : ""}` : "not yet"}.
            </p>
            <p>Past the period right now: {describe(status.data.past_the_period as unknown as Record<string, number>)}.</p>
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" variant="outline" disabled={!anyPending || run.isPending} onClick={removeNow}>
                {run.isPending ? "Removing…" : "Remove it now"}
              </Button>
              <span className="text-xs text-muted-foreground">The daily run does the same.</span>
            </div>
            <p className="text-xs text-muted-foreground">Kept: {status.data.keeps.join(" ")}</p>
          </div>
        ) : null}

        {canErase && (
          <div className="space-y-2 border-t pt-4">
            <p className="font-medium">Erase one person&apos;s data</p>
            <p className="text-xs text-muted-foreground">For someone who asks. Removes their comments, conversations and messages and the text of replies to them. A lead made from their enquiry stays in the CRM, which has to be handled there.</p>
            <div className="flex flex-wrap items-end gap-2">
              <div className="space-y-1">
                <Label htmlFor="erase-handle">Instagram handle</Label>
                <Input id="erase-handle" className="w-56" maxLength={100} placeholder="their_handle" value={handle} onChange={(e) => { setHandle(e.target.value); setFound(null); }} />
              </div>
              <Button size="sm" variant="outline" disabled={!handle.trim() || erase.isPending} onClick={count}>
                See what would be erased
              </Button>
            </div>
            {found && (
              <div role="alert" className="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900">
                <p>
                  @{found.handle.replace(/^@/, "")}: {found.result.comments} comment(s), {found.result.conversations} conversation(s) with {found.result.messages} message(s), {found.result.reply_texts} reply text(s).
                  {found.result.crm_leads > 0 ? ` ${found.result.crm_leads} CRM lead(s) were made from their enquiries and stay in the CRM.` : ""}
                </p>
                {found.result.comments + found.result.conversations + found.result.reply_texts === 0 ? (
                  <p>Nothing to erase.</p>
                ) : (
                  <Button size="sm" variant="destructive" disabled={erase.isPending} onClick={confirmErase}>
                    {erase.isPending ? "Erasing…" : "Erase it permanently"}
                  </Button>
                )}
              </div>
            )}
          </div>
        )}
        {notice && (
          <p role={notice.ok ? "status" : "alert"} className={notice.ok ? "text-emerald-800" : "text-destructive"}>
            {notice.text}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

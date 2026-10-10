import { ExternalLink } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { Post } from "@/features/social-media/api/social-media-api";
import { useAttempts, useQueue, useReconcile, useResolve, useRetry, useUnschedule } from "@/features/social-media/api/social-media-hooks";
import { ScheduleDialog } from "@/features/social-media/components/schedule-dialog";
import { FORMAT_LABEL, STATUS_LABEL, STATUS_VARIANT, errorMessage, formatInZone } from "@/features/social-media/lib/format";
import { safeHref } from "@/features/social-media/lib/links";

function History({ postId, timeZone }: { postId: string; timeZone: string }) {
  const attempts = useAttempts(postId);
  if (attempts.isLoading) return <Skeleton className="h-10 w-full" />;
  if (!attempts.data?.length) return <p className="text-xs text-muted-foreground">No publishing attempts yet.</p>;
  return (
    <ul className="space-y-1 text-xs">
      {attempts.data.map((a) => (
        <li key={a.id} className="rounded border p-2">
          <span className="font-medium">Attempt {a.attempt_no}</span> · {a.status} · {formatInZone(a.created_at, timeZone)}
          {a.publish_started_at && <span> · the post-creating call was sent</span>}
          {a.error && <div className={a.status === "retry" ? "text-muted-foreground" : "text-destructive"}>{a.error}</div>}
          {a.media_id && <div className="text-muted-foreground">Instagram media id {a.media_id}</div>}
        </li>
      ))}
    </ul>
  );
}

/** Everything waiting to go out, going out now, failed, or with an outcome nobody could confirm. */
export function QueueTab() {
  const queue = useQueue();
  const me = useMyRoles();
  const unschedule = useUnschedule();
  const retry = useRetry();
  const reconcile = useReconcile();
  const resolve = useResolve();
  const [openId, setOpenId] = useState<string | null>(null);
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [resolving, setResolving] = useState<Post | null>(null);
  const [mediaId, setMediaId] = useState("");
  const [permalink, setPermalink] = useState("");
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  const canPublish = (me.data?.is_superuser ?? false) || (me.data?.effective_permissions ?? []).includes("social_media.publish");
  const timeZone = queue.data?.timezone ?? "Asia/Kolkata";
  const busy = unschedule.isPending || retry.isPending || reconcile.isPending || resolve.isPending;

  const fail = (e: unknown) => setNotice({ ok: false, text: errorMessage(e, "That didn't work.") });

  function check(post: Post) {
    setNotice(null);
    reconcile.mutate(post.id, {
      onSuccess: (r) => {
        const text =
          r.outcome === "published"
            ? "Instagram confirms it was published. The post is now marked published."
            : r.outcome === "not_published"
              ? "Instagram confirms it was not published. It is marked failed and can be retried."
              : `Instagram couldn't settle it: ${r.note} Look at the profile, then use "Resolve".`;
        setNotice({ ok: r.outcome !== "unknown", text });
      },
      onError: fail,
    });
  }

  function doResolve(published: boolean) {
    if (!resolving) return;
    setResolveError(null);
    resolve.mutate(
      { id: resolving.id, published, mediaId: mediaId.trim(), permalink: permalink.trim() },
      {
        onSuccess: () => {
          setResolving(null);
          setNotice({ ok: true, text: published ? "Recorded as published." : "Recorded as not published. You can retry it." });
        },
        onError: (e) => setResolveError(errorMessage(e, "Couldn't record that.")),
      },
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">{queue.data?.worker_note ?? "Posts waiting to go out, and any that need you."}</p>
      {notice && (
        <p role={notice.ok ? "status" : "alert"} className={notice.ok ? "rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900" : "rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"}>
          {notice.text}
        </p>
      )}
      {queue.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : queue.isError ? (
        <p className="text-sm text-destructive">Couldn&apos;t load the queue.</p>
      ) : queue.data && queue.data.items.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">Nothing is waiting, failed or unclear. Scheduled posts appear here.</CardContent>
        </Card>
      ) : (
        queue.data?.items.map(({ post, last_attempt }) => (
          <Card key={post.id}>
            <CardContent className="space-y-2 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium">{post.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {FORMAT_LABEL[post.format]}
                    {post.scheduled_at ? ` · ${post.status === "scheduled" ? "goes out" : "was due"} ${formatInZone(post.scheduled_at, timeZone)}` : ""}
                    {post.status === "scheduled" && post.next_attempt_at ? ` · next try ${formatInZone(post.next_attempt_at, timeZone)}` : ""}
                    {post.attempt_count ? ` · ${post.attempt_count} attempt(s)` : ""}
                  </p>
                </div>
                <Badge variant={STATUS_VARIANT[post.status]}>{STATUS_LABEL[post.status]}</Badge>
              </div>
              {post.last_error && <p className={post.status === "scheduled" ? "text-xs text-muted-foreground" : "text-sm text-destructive"}>{post.last_error}</p>}
              {post.status === "publish_unknown" && (
                <p className="text-xs text-amber-800">
                  Instagram may or may not have published this. It will not be sent again until you have checked. Use &quot;Check with Instagram&quot; or look at the profile yourself.
                </p>
              )}
              {last_attempt && post.status !== "scheduled" && post.status !== "publishing" && <p className="text-xs text-muted-foreground">Last attempt: {last_attempt.status}.</p>}
              <div className="flex flex-wrap gap-2">
                {canPublish && post.status === "scheduled" && (
                  <>
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => setOpenId(post.id)}>
                      Move or publish now
                    </Button>
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => unschedule.mutate(post.id, { onError: fail })}>
                      Take off the schedule
                    </Button>
                  </>
                )}
                {post.status === "publishing" && <span className="self-center text-xs text-muted-foreground">Being published now. If this stays here for more than ten minutes it is checked automatically.</span>}
                {canPublish && post.status === "failed" && (
                  <Button size="sm" disabled={busy} onClick={() => window.confirm("Put this post back in the queue? It is confirmed not to be on Instagram.") && retry.mutate(post.id, { onError: fail, onSuccess: () => setNotice({ ok: true, text: "Back in the queue. It goes out within about a minute." }) })}>
                    Retry
                  </Button>
                )}
                {canPublish && post.status === "publish_unknown" && (
                  <>
                    <Button size="sm" disabled={busy} onClick={() => check(post)}>
                      {reconcile.isPending && reconcile.variables === post.id ? "Checking..." : "Check with Instagram"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() => {
                        setResolving(post);
                        setMediaId("");
                        setPermalink("");
                        setResolveError(null);
                      }}
                    >
                      Resolve by hand
                    </Button>
                  </>
                )}
                <Button size="sm" variant="ghost" onClick={() => setHistoryId(historyId === post.id ? null : post.id)}>
                  {historyId === post.id ? "Hide history" : "History"}
                </Button>
                {post.external_permalink && (
                  <a className="inline-flex h-9 items-center gap-1 text-sm text-primary underline" href={safeHref(post.external_permalink)} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-3.5 w-3.5" /> On Instagram
                  </a>
                )}
              </div>
              {historyId === post.id && <History postId={post.id} timeZone={timeZone} />}
            </CardContent>
          </Card>
        ))
      )}

      <ScheduleDialog postId={openId} onOpenChange={(open) => !open && setOpenId(null)} />

      <Dialog open={resolving !== null} onOpenChange={(open) => !open && setResolving(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Resolve: {resolving?.title}</DialogTitle>
            <DialogDescription>Open the Instagram profile and look. Record what you see. This is your decision, and it is recorded.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <div className="space-y-1.5">
              <Label htmlFor="rs-link">Link to the post (if it is there)</Label>
              <Input id="rs-link" placeholder="https://www.instagram.com/p/..." value={permalink} onChange={(e) => setPermalink(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="rs-media">Instagram media id (optional)</Label>
              <Input id="rs-media" value={mediaId} onChange={(e) => setMediaId(e.target.value)} />
            </div>
            {resolveError && <p role="alert" className="text-destructive">{resolveError}</p>}
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" disabled={resolve.isPending} onClick={() => doResolve(false)}>
              It is NOT on Instagram
            </Button>
            <Button disabled={resolve.isPending} onClick={() => doResolve(true)}>
              It IS on Instagram
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

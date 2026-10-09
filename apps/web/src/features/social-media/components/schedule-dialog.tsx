import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import { usePost, usePublishNow, useReadiness, useSchedule, useUnschedule } from "@/features/social-media/api/social-media-hooks";
import { STATUS_LABEL, STATUS_VARIANT, errorMessage, formatInZone, toInputValue } from "@/features/social-media/lib/format";

interface Props {
  postId: string | null;
  onOpenChange: (open: boolean) => void;
}

/**
 * Schedules an approved post, moves or cancels its schedule, or publishes it now. It shows exactly what would be posted
 * and everything that currently stops it, and publishing to Instagram needs an explicit confirmation.
 */
export function ScheduleDialog({ postId, onOpenChange }: Props) {
  const post = usePost(postId);
  const readiness = useReadiness(postId);
  const me = useMyRoles();
  const schedule = useSchedule();
  const unschedule = useUnschedule();
  const publishNow = usePublishNow();
  const [when, setWhen] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const canPublish = (me.data?.is_superuser ?? false) || (me.data?.effective_permissions ?? []).includes("social_media.publish");
  const data = post.data;
  const info = readiness.data;
  const timeZone = info?.timezone ?? "Asia/Kolkata";

  useEffect(() => {
    setConfirmed(false);
    setMessage(null);
    setWhen("");
  }, [postId]);

  useEffect(() => {
    if (data && !when && data.scheduled_at) setWhen(toInputValue(data.scheduled_at, timeZone));
    // Fill the field once, when the post has loaded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.id, timeZone]);

  const busy = schedule.isPending || unschedule.isPending || publishNow.isPending;
  const isScheduled = data?.status === "scheduled";
  const canAct = data && (data.status === "approved" || data.status === "scheduled");

  function run<T>(mutation: { mutate: (v: T, o: { onSuccess: () => void; onError: (e: unknown) => void }) => void }, variables: T, done: string) {
    setMessage(null);
    mutation.mutate(variables, {
      onSuccess: () => {
        setMessage({ ok: true, text: done });
        setConfirmed(false);
      },
      onError: (e) => setMessage({ ok: false, text: errorMessage(e, "That didn't work.") }),
    });
  }

  return (
    <Dialog open={postId !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{data ? data.title : "Schedule or publish"}</DialogTitle>
          <DialogDescription>Nothing goes to Instagram unless the post is approved and someone with the publish permission confirms it here.</DialogDescription>
        </DialogHeader>

        {post.isLoading || readiness.isLoading || !data || !info ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <div className="space-y-4 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={STATUS_VARIANT[data.status]}>{STATUS_LABEL[data.status]}</Badge>
              {data.scheduled_at && <span className="text-muted-foreground">for {formatInZone(data.scheduled_at, timeZone)} ({timeZone})</span>}
            </div>

            {data.artwork?.files?.[0]?.url && (
              <img src={data.artwork.files[0].url ?? undefined} alt={`Artwork for ${data.title}`} className="max-h-64 rounded border" />
            )}

            <div>
              <p className="mb-1 font-medium">The caption that will be posted</p>
              <pre className="whitespace-pre-wrap rounded-md border bg-muted/40 p-3 font-sans">{info.caption || "(none: Stories are published without a caption)"}</pre>
              <p className="mt-1 text-xs text-muted-foreground">
                {info.caption_length}/{info.caption_limit} characters. {info.note}
              </p>
            </div>

            {info.problems.length > 0 && (
              <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900">
                <p className="mb-1 font-medium">Not ready yet</p>
                <ul className="list-disc space-y-0.5 pl-5">
                  {info.problems.map((p) => (
                    <li key={p}>{p}</li>
                  ))}
                </ul>
              </div>
            )}

            {!canPublish ? (
              <p className="text-muted-foreground">Scheduling and publishing need the social_media.publish permission.</p>
            ) : !canAct ? (
              <p className="text-muted-foreground">Only an approved post can be scheduled or published.</p>
            ) : (
              <fieldset disabled={busy} className="space-y-4">
                {info.publish_mode === "scheduled" ? (
                  <div className="space-y-1.5">
                    <Label htmlFor="sd-when">Publish at ({timeZone})</Label>
                    <div className="flex flex-wrap gap-2">
                      <Input id="sd-when" type="datetime-local" className="max-w-xs" value={when} onChange={(e) => setWhen(e.target.value)} />
                      <Button
                        onClick={() => run(schedule, { id: data.id, scheduledAt: when }, isScheduled ? "Rescheduled." : "Scheduled.")}
                        disabled={!when || info.problems.length > 0}
                      >
                        {isScheduled ? "Move to this time" : "Schedule"}
                      </Button>
                      {isScheduled && (
                        <Button variant="outline" onClick={() => run(unschedule, data.id, "Taken off the schedule. The post is approved but not scheduled.")}>
                          Take off the schedule
                        </Button>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">At least 5 minutes ahead. The worker checks every minute, so it goes out within about a minute of this time.</p>
                  </div>
                ) : (
                  <p className="text-muted-foreground">Scheduling is switched off, so posts are published by hand. You can change this under Settings, &quot;After a post is approved&quot;.</p>
                )}

                <div className="space-y-2 rounded-md border p-3">
                  <p className="font-medium">Publish now</p>
                  <label className="flex items-start gap-2">
                    <input type="checkbox" className="mt-1" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
                    <span>I have checked the picture and caption above and want this posted to Instagram now. This can&apos;t be undone from here.</span>
                  </label>
                  <Button onClick={() => run(publishNow, data.id, "Queued. It goes out within about a minute: watch the Queue tab.")} disabled={!confirmed || info.problems.length > 0}>
                    Publish now
                  </Button>
                </div>
              </fieldset>
            )}

            {message && (
              <p role={message.ok ? "status" : "alert"} className={message.ok ? "text-emerald-700" : "text-destructive"}>
                {message.text}
              </p>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

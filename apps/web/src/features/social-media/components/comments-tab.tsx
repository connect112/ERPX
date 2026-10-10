import { ExternalLink } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { CommentView, InboxComment } from "@/features/social-media/api/social-media-api";
import { useComments, useMarkHandled } from "@/features/social-media/api/social-media-hooks";
import { InboxStatus, ReplyHistory } from "@/features/social-media/components/inbox-status";
import { TriageBadges } from "@/features/social-media/components/inbox-parts";
import { CreateLeadDialog, type LeadTarget } from "@/features/social-media/components/create-lead-dialog";
import { useCanCreateLead } from "@/features/social-media/lib/use-can-create-lead";
import { ReplyDialog, type ReplyTarget } from "@/features/social-media/components/reply-dialog";
import { errorMessage, formatInZone } from "@/features/social-media/lib/format";

const VIEWS: { value: CommentView; label: string }[] = [
  { value: "unanswered", label: "Unanswered" },
  { value: "enquiries", label: "Enquiries" },
  { value: "complaints", label: "Complaints" },
  { value: "recent", label: "Recent" },
  { value: "spam", label: "Possible spam" },
  { value: "all", label: "All" },
];

const PAGE = 20;

function toTarget(comment: InboxComment): ReplyTarget {
  return {
    id: comment.id,
    kind: "comment",
    from: comment.author_username ?? "unknown",
    theirText: comment.text,
    triage: comment.triage,
    suggestion: comment.suggestion,
  };
}

/** Comments on your recent posts. Replying is always a person's decision and action. */
export function CommentsTab() {
  const [view, setView] = useState<CommentView>("unanswered");
  const [search, setSearch] = useState("");
  const [skip, setSkip] = useState(0);
  const [target, setTarget] = useState<ReplyTarget | null>(null);
  const [leadTarget, setLeadTarget] = useState<LeadTarget | null>(null);
  const canLead = useCanCreateLead();
  const [error, setError] = useState<string | null>(null);
  const comments = useComments({ view, q: search.trim() || undefined, skip, limit: PAGE });
  const me = useMyRoles();
  const mark = useMarkHandled("comment");
  const canReply = (me.data?.is_superuser ?? false) || (me.data?.effective_permissions ?? []).includes("social_media.reply");
  const total = comments.data?.total ?? 0;

  function handled(id: string, action: "ignore" | "reopen") {
    setError(null);
    mark.mutate({ id, action }, { onError: (e) => setError(errorMessage(e, "That didn't work.")) });
  }

  return (
    <div className="space-y-4">
      <InboxStatus part="comments" />
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex max-w-full gap-1 overflow-x-auto" role="group" aria-label="Filter comments">
          {VIEWS.map((v) => (
            <Button key={v.value} size="sm" variant={view === v.value ? "default" : "outline"} onClick={() => { setView(v.value); setSkip(0); }}>
              {v.label}
            </Button>
          ))}
        </div>
        <Input className="w-full sm:w-56" placeholder="Search comments" aria-label="Search comments" value={search} onChange={(e) => { setSearch(e.target.value); setSkip(0); }} />
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {!canReply && <p className="text-xs text-muted-foreground">You can read comments but replying needs the social_media.reply permission.</p>}

      {comments.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : comments.isError ? (
        <p className="text-sm text-destructive">Couldn&apos;t load comments.</p>
      ) : comments.data && comments.data.items.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">No comments here. New ones appear after Instagram is read.</CardContent>
        </Card>
      ) : (
        comments.data?.items.map((c) => (
          <Card key={c.id}>
            <CardContent className="space-y-3 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                  <span className="font-medium">@{c.author_username ?? "unknown"}</span>
                  <TriageBadges triage={c.triage} />
                  {c.status === "answered" && <Badge variant="success">Answered</Badge>}
                  {c.status === "ignored" && <Badge variant="secondary">Set aside</Badge>}
                </div>
                <span className="text-xs text-muted-foreground">{formatInZone(c.posted_at, "Asia/Kolkata")}</span>
              </div>
              <p className="whitespace-pre-wrap break-words text-sm">{c.text}</p>
              {c.triage.care_reason && c.triage.needs_care && <p className="text-xs text-amber-800">{c.triage.care_reason}</p>}
              {c.suggestion.summary && <p className="text-xs text-muted-foreground">Summary (AI): {c.suggestion.summary}</p>}
              {c.media && (
                <p className="flex items-center gap-1 text-xs text-muted-foreground">
                  <span className="truncate">On: {c.media.caption ? c.media.caption.slice(0, 80) : "a post"}</span>
                  {c.media.permalink && (
                    <a href={c.media.permalink} target="_blank" rel="noreferrer" aria-label="Open the post on Instagram" className="shrink-0">
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </p>
              )}
              {c.replies.length > 0 && (
                <ul className="space-y-1 border-l-2 pl-3 text-sm">
                  {c.replies.map((r) => (
                    <li key={r.id}>
                      <span className="text-xs text-muted-foreground">
                        {r.by === "erpx" ? `Reply${r.sent_by ? ` by ${r.sent_by}` : ""}` : "Reply on Instagram"} · {r.status !== "sent" && r.by === "erpx" ? `${r.status} · ` : ""}
                        {formatInZone(r.at, "Asia/Kolkata")}
                      </span>
                      <p className="whitespace-pre-wrap break-words">{r.text}</p>
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex flex-wrap gap-2">
                {canReply && c.status !== "ignored" && (
                  <Button size="sm" onClick={() => setTarget(toTarget(c))}>
                    {c.status === "answered" ? "Reply again" : "Reply"}
                  </Button>
                )}
                {canLead && c.status !== "ignored" && (
                  <Button size="sm" variant="outline" onClick={() => setLeadTarget({ kind: "comment", id: c.id, handle: c.author_username ?? "unknown" })}>
                    Create lead
                  </Button>
                )}
                {c.status === "new" && (
                  <Button size="sm" variant="outline" onClick={() => handled(c.id, "ignore")} disabled={mark.isPending}>
                    Set aside
                  </Button>
                )}
                {c.status === "ignored" && (
                  <Button size="sm" variant="outline" onClick={() => handled(c.id, "reopen")} disabled={mark.isPending}>
                    Bring back
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))
      )}

      {total > PAGE && (
        <div className="flex items-center justify-between text-sm">
          <Button size="sm" variant="outline" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - PAGE))}>
            Previous
          </Button>
          <span className="text-xs text-muted-foreground">
            {skip + 1}–{Math.min(skip + PAGE, total)} of {total}
          </span>
          <Button size="sm" variant="outline" disabled={skip + PAGE >= total} onClick={() => setSkip(skip + PAGE)}>
            Next
          </Button>
        </div>
      )}

      <ReplyHistory kind="comment" />
      <ReplyDialog key={target?.id ?? "none"} target={target} onClose={() => setTarget(null)} />
      <CreateLeadDialog key={leadTarget?.id ?? "no-lead"} target={leadTarget} onClose={() => setLeadTarget(null)} />
    </div>
  );
}

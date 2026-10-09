import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { Conversation, ConversationView } from "@/features/social-media/api/social-media-api";
import { useConversations, useMarkHandled, useThread } from "@/features/social-media/api/social-media-hooks";
import { InboxStatus, ReplyHistory } from "@/features/social-media/components/inbox-status";
import { TriageBadges } from "@/features/social-media/components/inbox-parts";
import { CreateLeadDialog, type LeadTarget } from "@/features/social-media/components/create-lead-dialog";
import { useCanCreateLead } from "@/features/social-media/lib/use-can-create-lead";
import { ReplyDialog, type ReplyTarget } from "@/features/social-media/components/reply-dialog";
import { errorMessage, formatInZone } from "@/features/social-media/lib/format";

const VIEWS: { value: ConversationView; label: string }[] = [
  { value: "needs_reply", label: "Needs a reply" },
  { value: "high_priority", label: "High priority" },
  { value: "enquiries", label: "Enquiries" },
  { value: "complaints", label: "Complaints" },
  { value: "all", label: "All" },
];

const PAGE = 20;
const ZONE = "Asia/Kolkata";

function windowText(c: Conversation): string {
  if (!c.participant_known) return "Can't reply from here (the person isn't known yet)";
  if (!c.window_open) return "The 24-hour reply window has closed. Reply from the Instagram app.";
  return `Can reply until ${formatInZone(c.window_expires_at, ZONE)}`;
}

function Thread({ id, onReply, onLead, canReply, canLead, onClose }: { id: string; onReply: (target: ReplyTarget) => void; onLead: (target: LeadTarget) => void; canReply: boolean; canLead: boolean; onClose: () => void }) {
  const thread = useThread(id);
  const data = thread.data;
  const conversation = data?.conversation;
  const lastIncoming = [...(data?.messages ?? [])].reverse().find((m) => m.direction === "in");
  const canSend = canReply && !!conversation && conversation.window_open && conversation.participant_known;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>@{conversation?.participant_username ?? "conversation"}</DialogTitle>
          <DialogDescription>{conversation ? windowText(conversation) : "Loading…"}</DialogDescription>
        </DialogHeader>
        {thread.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : thread.isError || !data || !conversation ? (
          <p className="text-sm text-destructive">Couldn&apos;t load this conversation.</p>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">Only the 20 most recent messages can be read from Instagram.</p>
            <ul className="space-y-2" aria-label="Messages">
              {data.messages.map((m) => (
                <li key={m.id} className={`max-w-[85%] rounded-lg border p-2 text-sm ${m.direction === "out" ? "ml-auto bg-primary/10" : "bg-muted/40"}`}>
                  <p className="whitespace-pre-wrap break-words">{m.text ?? "[attachment or unsupported message]"}</p>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {m.direction === "out" ? "You" : `@${conversation.participant_username ?? "them"}`} · {formatInZone(m.sent_at, ZONE)}
                  </p>
                </li>
              ))}
            </ul>
            {conversation.suggestion.summary && <p className="text-xs text-muted-foreground">Summary (AI): {conversation.suggestion.summary}</p>}
            {conversation.triage.needs_care && conversation.triage.care_reason && <p className="text-xs text-amber-800">{conversation.triage.care_reason}</p>}
            {canReply && (
              <Button
                disabled={!canSend}
                onClick={() =>
                  onReply({
                    id: conversation.id,
                    kind: "dm",
                    from: conversation.participant_username ?? "unknown",
                    theirText: lastIncoming?.text ?? conversation.preview ?? "",
                    triage: conversation.triage,
                    suggestion: conversation.suggestion,
                  })
                }
              >
                Reply
              </Button>
            )}
            {canLead && (
              <Button variant="outline" onClick={() => onLead({ kind: "dm", id: conversation.id, handle: conversation.participant_username ?? "unknown" })}>
                Create lead
              </Button>
            )}
            {!canReply && <p className="text-xs text-muted-foreground">Replying needs the social_media.reply permission.</p>}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Direct messages. A message is sent only by a person pressing Send, and only inside Instagram's 24-hour window. */
export function MessagesTab() {
  const [view, setView] = useState<ConversationView>("needs_reply");
  const [search, setSearch] = useState("");
  const [skip, setSkip] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const [target, setTarget] = useState<ReplyTarget | null>(null);
  const [leadTarget, setLeadTarget] = useState<LeadTarget | null>(null);
  const canLead = useCanCreateLead();
  const [error, setError] = useState<string | null>(null);
  const conversations = useConversations({ view, q: search.trim() || undefined, skip, limit: PAGE });
  const me = useMyRoles();
  const mark = useMarkHandled("dm");
  const canReply = (me.data?.is_superuser ?? false) || (me.data?.effective_permissions ?? []).includes("social_media.reply");
  const total = conversations.data?.total ?? 0;

  function handled(id: string, action: "ignore" | "reopen") {
    setError(null);
    mark.mutate({ id, action }, { onError: (e) => setError(errorMessage(e, "That didn't work.")) });
  }

  return (
    <div className="space-y-4">
      <InboxStatus part="messages" />
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex max-w-full gap-1 overflow-x-auto" role="group" aria-label="Filter conversations">
          {VIEWS.map((v) => (
            <Button key={v.value} size="sm" variant={view === v.value ? "default" : "outline"} onClick={() => { setView(v.value); setSkip(0); }}>
              {v.label}
            </Button>
          ))}
        </div>
        <Input className="w-full sm:w-56" placeholder="Search by username" aria-label="Search conversations" value={search} onChange={(e) => { setSearch(e.target.value); setSkip(0); }} />
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

      {conversations.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : conversations.isError ? (
        <p className="text-sm text-destructive">Couldn&apos;t load messages.</p>
      ) : conversations.data && conversations.data.items.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">No conversations here.</CardContent>
        </Card>
      ) : (
        conversations.data?.items.map((c) => (
          <Card key={c.id}>
            <CardContent className="space-y-2 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                  <span className="font-medium">@{c.participant_username ?? "unknown"}</span>
                  <TriageBadges triage={c.triage} />
                  {c.status === "answered" && <Badge variant="success">Answered</Badge>}
                  {c.status === "ignored" && <Badge variant="secondary">Set aside</Badge>}
                </div>
                <span className="text-xs text-muted-foreground">{formatInZone(c.last_message_at, ZONE)}</span>
              </div>
              {c.preview && <p className="line-clamp-2 break-words text-sm">{c.preview}</p>}
              <p className="text-xs text-muted-foreground">{windowText(c)}</p>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={() => setOpenId(c.id)}>
                  Open
                </Button>
                {c.status === "open" && (
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

      <ReplyHistory kind="dm" />
      {openId && !target && !leadTarget && (
        <Thread
          id={openId}
          canReply={canReply}
          canLead={canLead}
          onLead={setLeadTarget}
          onClose={() => setOpenId(null)}
          onReply={(t) => {
            setTarget(t);
          }}
        />
      )}
      <CreateLeadDialog key={leadTarget?.id ?? "no-lead"} target={leadTarget} onClose={() => setLeadTarget(null)} />
      <ReplyDialog
        key={target?.id ?? "none"}
        target={target}
        onClose={() => {
          setTarget(null);
        }}
      />
    </div>
  );
}

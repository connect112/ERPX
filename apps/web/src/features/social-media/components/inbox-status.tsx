import { RefreshCw } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useInboxSummary, useReplyHistory, useSyncInbox } from "@/features/social-media/api/social-media-hooks";
import { ReplyStatusBadge, UnclearReply } from "@/features/social-media/components/inbox-parts";
import { SOURCE_LABEL } from "@/features/social-media/lib/inbox-labels";
import { errorMessage, formatInZone } from "@/features/social-media/lib/format";

const STAGE_LABEL: Record<string, string> = { media: "Posts", comments: "Comments", conversations: "Messages" };

/** Whether Instagram is connected, when it was last read, anything that failed, and a button to read it now. */
export function InboxStatus({ part }: { part: "comments" | "messages" }) {
  const summary = useInboxSummary();
  const sync = useSyncInbox();
  const [notice, setNotice] = useState<string | null>(null);
  const data = summary.data;
  const allowed = part === "comments" ? data?.can_read_comments : data?.can_read_messages;
  const failures = Object.entries(data?.stages ?? {}).filter(([, stage]) => stage.ok === false && stage.error);

  function refresh() {
    setNotice(null);
    sync.mutate(undefined, {
      onSuccess: (r) => setNotice(r.skipped ? (r.message ?? "Just read a moment ago.") : "Read the latest from Instagram."),
      onError: (e) => setNotice(errorMessage(e, "Couldn't read from Instagram.")),
    });
  }

  if (summary.isLoading) return <Skeleton className="h-12 w-full" />;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {!data?.connected
            ? "Instagram isn't connected. Connect it in Settings & Integrations to read comments and messages."
            : allowed === false
              ? "Instagram hasn't allowed this yet (see Settings & Integrations, Check what it can do)."
              : data.last_sync_at
                ? `Last read from Instagram ${formatInZone(data.last_sync_at, "Asia/Kolkata")}.`
                : "Not read from Instagram yet."}
        </p>
        <Button size="sm" variant="outline" onClick={refresh} disabled={sync.isPending || !data?.connected}>
          <RefreshCw className={`mr-1 h-3.5 w-3.5 ${sync.isPending ? "animate-spin" : ""}`} />
          {sync.isPending ? "Reading…" : "Read now"}
        </Button>
      </div>
      {notice && <p role="status" className="text-xs text-muted-foreground">{notice}</p>}
      {failures.map(([name, stage]) => (
        <p key={name} role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-2 text-xs text-destructive">
          {STAGE_LABEL[name] ?? name}: {stage.error}
        </p>
      ))}
      {data?.note && <p className="text-xs text-muted-foreground">{data.note}</p>}
    </div>
  );
}

/** Every reply anyone sent from here: who, the exact words, where the words came from, and how it ended. */
export function ReplyHistory({ kind }: { kind: "comment" | "dm" }) {
  const [open, setOpen] = useState(false);
  const history = useReplyHistory();
  const rows = (history.data ?? []).filter((r) => r.kind === kind);
  return (
    <div className="space-y-2">
      <Button size="sm" variant="ghost" onClick={() => setOpen(!open)}>
        {open ? "Hide" : "Show"} reply history{history.data ? ` (${rows.length})` : ""}
      </Button>
      {open &&
        (history.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing has been sent from here yet.</p>
        ) : (
          <div className="space-y-2">
            {rows.map((r) => (
              <Card key={r.id}>
                <CardContent className="space-y-2 p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs text-muted-foreground">
                      {r.sent_by ?? "Someone"} · {formatInZone(r.finished_at ?? r.created_at, "Asia/Kolkata")} · {SOURCE_LABEL[r.source]}
                      {r.acknowledged_sensitive ? " · confirmed handling personally" : ""}
                    </span>
                    <ReplyStatusBadge status={r.status} />
                  </div>
                  <p className="whitespace-pre-wrap break-words">{r.message}</p>
                  {r.status === "failed" && r.error && <p className="text-xs text-destructive">{r.error}</p>}
                  {(r.status === "unknown" || r.status === "pending") && <UnclearReply reply={r} />}
                </CardContent>
              </Card>
            ))}
          </div>
        ))}
    </div>
  );
}

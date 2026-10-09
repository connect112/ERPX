import { Copy, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { Post, PostPayload, TransitionAction } from "@/features/social-media/api/social-media-api";
import {
  useCreatePost,
  useDeletePost,
  useDuplicatePost,
  usePosts,
  useSocialSettings,
  useTransitionPost,
  useUpdatePost,
} from "@/features/social-media/api/social-media-hooks";
import { PostEditorDialog } from "@/features/social-media/components/post-editor-dialog";
import {
  FORMAT_LABEL,
  STATUS_LABEL,
  STATUS_VARIANT,
  VERIFICATION_LABEL,
  errorMessage,
  formatInZone,
} from "@/features/social-media/lib/format";

const STATUS_FILTERS = ["", "draft", "review", "approved", "scheduled", "published", "failed", "cancelled"] as const;
const NATIVE_SELECT = "h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring";

interface Props {
  initialStatus?: string;
}

export function PostsTab({ initialStatus = "" }: Props) {
  const [status, setStatus] = useState(initialStatus);
  const [search, setSearch] = useState("");
  const posts = usePosts({ status: status || undefined, q: search || undefined, limit: 50 });
  const settings = useSocialSettings();
  const me = useMyRoles();
  const create = useCreatePost();
  const update = useUpdatePost();
  const remove = useDeletePost();
  const duplicate = useDuplicatePost();
  const transition = useTransitionPost();

  const [editing, setEditing] = useState<Post | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [approving, setApproving] = useState<Post | null>(null);
  const [ackWarnings, setAckWarnings] = useState(false);
  const [ackRisk, setAckRisk] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const permissions = me.data?.effective_permissions ?? [];
  const isSuper = me.data?.is_superuser ?? false;
  const canManage = isSuper || permissions.includes("social_media.manage");
  const canApprove = isSuper || permissions.includes("social_media.approve");
  const timeZone = settings.data?.timezone ?? "Asia/Kolkata";
  const labelOf = (key: string | null) => settings.data?.pillars.find((p) => p.key === key)?.label ?? key;

  function openEditor(post: Post | null) {
    setEditing(post);
    setEditorError(null);
    setEditorOpen(true);
  }

  function save(payload: PostPayload) {
    setEditorError(null);
    const done = (post: Post) => {
      setEditorOpen(false);
      setNotice(post.approval_withdrawn ? "Saved. The earlier approval was withdrawn because the content changed." : "Saved.");
    };
    if (editing) {
      update.mutate({ id: editing.id, payload }, { onSuccess: done, onError: (e) => setEditorError(errorMessage(e, "Couldn't save the post.")) });
    } else {
      create.mutate(payload, { onSuccess: done, onError: (e) => setEditorError(errorMessage(e, "Couldn't save the post.")) });
    }
  }

  function act(post: Post, action: TransitionAction) {
    setActionError(null);
    transition.mutate(
      { id: post.id, action },
      { onSuccess: () => setNotice("Done."), onError: (e) => setActionError(errorMessage(e, "That didn't work.")) },
    );
  }

  function openApprove(post: Post) {
    setApproving(post);
    setAckWarnings(false);
    setAckRisk(false);
    setApproveError(null);
  }

  function confirmApprove() {
    if (!approving) return;
    transition.mutate(
      { id: approving.id, action: "approve", acknowledge_warnings: ackWarnings, acknowledge_high_risk: ackRisk },
      {
        onSuccess: () => {
          setApproving(null);
          setNotice("Approved. It is not published: publishing arrives with the next phases.");
        },
        onError: (e) => setApproveError(errorMessage(e, "Couldn't approve the post.")),
      },
    );
  }

  const busy = transition.isPending || remove.isPending || duplicate.isPending;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="Filter by status" className={NATIVE_SELECT} value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {s ? STATUS_LABEL[s] : "All statuses"}
            </option>
          ))}
        </select>
        <Input className="max-w-xs" placeholder="Search titles" value={search} onChange={(e) => setSearch(e.target.value)} />
        <div className="flex-1" />
        {canManage && (
          <Button onClick={() => openEditor(null)}>
            <Plus className="mr-1 h-4 w-4" /> New draft
          </Button>
        )}
      </div>

      {notice && (
        <p role="status" className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">
          {notice}
        </p>
      )}
      {actionError && (
        <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
          {actionError}
        </p>
      )}

      {posts.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : posts.isError ? (
        <p className="text-sm text-destructive">Couldn&apos;t load posts. Try again in a moment.</p>
      ) : posts.data && posts.data.items.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            {status || search ? "No posts match this filter." : "No posts yet. Write your first draft to start the approval workflow."}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {posts.data?.items.map((post) => (
            <Card key={post.id}>
              <CardContent className="space-y-3 p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-medium">{post.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {FORMAT_LABEL[post.format]}
                      {post.pillar ? ` · ${labelOf(post.pillar)}` : ""}
                      {post.scheduled_at ? ` · planned ${formatInZone(post.scheduled_at, timeZone)}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge variant={STATUS_VARIANT[post.status]}>{STATUS_LABEL[post.status]}</Badge>
                    {post.verification_status !== "not_required" && (
                      <Badge variant={post.verification_status === "verified" ? "success" : "warning"}>
                        {VERIFICATION_LABEL[post.verification_status]}
                      </Badge>
                    )}
                    {post.high_risk && <Badge variant="destructive">High risk</Badge>}
                    {post.time_sensitive && <Badge variant="warning">Time-sensitive</Badge>}
                  </div>
                </div>
                {post.content.caption && <p className="line-clamp-2 text-sm text-muted-foreground">{post.content.caption}</p>}
                {post.warnings.length > 0 && (
                  <ul className="space-y-1 text-xs">
                    {post.warnings.map((w, i) => (
                      <li key={i} className={w.severity === "blocking" ? "text-destructive" : "text-amber-700"}>
                        {w.severity === "blocking" ? "Blocking: " : "Warning: "}
                        {w.message}
                      </li>
                    ))}
                  </ul>
                )}
                {post.last_error && <p className="text-xs text-destructive">{post.last_error}</p>}
                {canManage && (
                  <div className="flex flex-wrap gap-2">
                    {["draft", "review", "approved", "cancelled", "failed"].includes(post.status) && post.status !== "cancelled" && (
                      <Button size="sm" variant="outline" onClick={() => openEditor(post)}>
                        <Pencil className="mr-1 h-3.5 w-3.5" /> Edit
                      </Button>
                    )}
                    {post.status === "draft" && (
                      <Button size="sm" disabled={busy} onClick={() => act(post, "submit")}>
                        Submit for review
                      </Button>
                    )}
                    {post.status === "review" && (
                      <>
                        <Button size="sm" variant="outline" disabled={busy} onClick={() => act(post, "request_changes")}>
                          Request changes
                        </Button>
                        {canApprove ? (
                          <Button size="sm" disabled={busy} onClick={() => openApprove(post)}>
                            Review and approve
                          </Button>
                        ) : (
                          <span className="self-center text-xs text-muted-foreground">Waiting for someone who can approve.</span>
                        )}
                      </>
                    )}
                    {post.status === "approved" && canApprove && (
                      <Button size="sm" variant="outline" disabled={busy} onClick={() => act(post, "unapprove")}>
                        Withdraw approval
                      </Button>
                    )}
                    {["draft", "review", "approved", "failed"].includes(post.status) && (
                      <Button size="sm" variant="outline" disabled={busy} onClick={() => act(post, "cancel")}>
                        Cancel post
                      </Button>
                    )}
                    {["cancelled", "failed"].includes(post.status) && (
                      <Button size="sm" variant="outline" disabled={busy} onClick={() => act(post, "reopen")}>
                        Reopen as draft
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() => duplicate.mutate(post.id, { onSuccess: () => setNotice("Duplicated as a new draft."), onError: (e) => setActionError(errorMessage(e, "Couldn't duplicate.")) })}
                    >
                      <Copy className="mr-1 h-3.5 w-3.5" /> Duplicate
                    </Button>
                    {["draft", "cancelled"].includes(post.status) && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy}
                        onClick={() => {
                          if (window.confirm(`Delete "${post.title}"? This can't be undone.`))
                            remove.mutate(post.id, { onSuccess: () => setNotice("Deleted."), onError: (e) => setActionError(errorMessage(e, "Couldn't delete.")) });
                        }}
                      >
                        <Trash2 className="mr-1 h-3.5 w-3.5" /> Delete
                      </Button>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <PostEditorDialog
        open={editorOpen}
        onOpenChange={setEditorOpen}
        post={editing}
        pillars={settings.data?.pillars ?? []}
        timeZone={timeZone}
        canVerify={canApprove}
        saving={create.isPending || update.isPending}
        error={editorError}
        onSave={save}
      />

      <Dialog open={approving !== null} onOpenChange={(open) => !open && setApproving(null)}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Approve this post?</DialogTitle>
            <DialogDescription>
              Approving records that you reviewed exactly this content. Any later edit withdraws the approval.
            </DialogDescription>
          </DialogHeader>
          {approving && (
            <div className="space-y-3 text-sm">
              <div className="rounded-md border p-3">
                {approving.content.headline && <p className="font-medium">{approving.content.headline}</p>}
                <p className="whitespace-pre-wrap">{approving.content.caption}</p>
                {approving.content.cta && <p className="mt-2 text-muted-foreground">{approving.content.cta}</p>}
                {approving.content.hashtags.length > 0 && (
                  <p className="mt-2 text-muted-foreground">{approving.content.hashtags.map((h) => `#${h}`).join(" ")}</p>
                )}
              </div>
              {approving.sources.length > 0 && (
                <ul className="list-disc space-y-0.5 pl-5 text-xs">
                  {approving.sources.map((s) => (
                    <li key={s.url}>
                      <a className="text-primary underline" href={s.url} target="_blank" rel="noreferrer noopener">
                        {s.title || s.url}
                      </a>
                      {s.published_at ? ` (${s.published_at})` : ""}
                    </li>
                  ))}
                </ul>
              )}
              {approving.warnings.length > 0 && (
                <label className="flex items-start gap-2">
                  <input type="checkbox" className="mt-1" checked={ackWarnings} onChange={(e) => setAckWarnings(e.target.checked)} />
                  <span>I have read the {approving.warnings.length} warning(s) on this post.</span>
                </label>
              )}
              {(approving.high_risk || approving.time_sensitive) && (
                <label className="flex items-start gap-2">
                  <input type="checkbox" className="mt-1" checked={ackRisk} onChange={(e) => setAckRisk(e.target.checked)} />
                  <span>I have checked this post&apos;s high-risk or time-sensitive claims against the sources myself.</span>
                </label>
              )}
              {approveError && <p className="text-destructive">{approveError}</p>}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setApproving(null)}>
              Cancel
            </Button>
            <Button onClick={confirmApprove} disabled={transition.isPending}>
              {transition.isPending ? "Approving..." : "Approve"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

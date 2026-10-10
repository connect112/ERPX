import { CalendarClock, Copy, ExternalLink, ImageIcon, Pencil, Plus, ShieldCheck, Trash2, Wand2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { Post, PostPayload, RewriteElement, TransitionAction } from "@/features/social-media/api/social-media-api";
import {
  useCheckPost,
  useCreatePost,
  useDeletePost,
  useDuplicatePost,
  usePosts,
  useRewrite,
  useSocialSettings,
  useTransitionPost,
  useUpdatePost,
} from "@/features/social-media/api/social-media-hooks";
import { ArtworkDialog } from "@/features/social-media/components/artwork-dialog";
import { GridPreview } from "@/features/social-media/components/grid-preview";
import { PostEditorDialog } from "@/features/social-media/components/post-editor-dialog";
import { ScheduleDialog } from "@/features/social-media/components/schedule-dialog";
import { safeHref } from "@/features/social-media/lib/links";
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
const REWRITE_LABEL: Record<RewriteElement, string> = {
  hooks: "Hooks",
  headline: "Headline",
  caption: "Caption",
  cta: "Call to action",
  hashtags: "Hashtags",
  thumbnail_text: "Cover text",
  visual_direction: "Visual direction",
  alt_text: "Alt text",
};

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
  const check = useCheckPost();
  const rewrite = useRewrite();
  const [rewriting, setRewriting] = useState<Post | null>(null);
  const [artworkId, setArtworkId] = useState<string | null>(null);
  const [scheduleId, setScheduleId] = useState<string | null>(null);
  const [element, setElement] = useState<RewriteElement>("caption");
  const [instruction, setInstruction] = useState("");
  const [rewriteError, setRewriteError] = useState<string | null>(null);

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

  function runCheck(post: Post) {
    setActionError(null);
    check.mutate(post.id, {
      onSuccess: (p) => setNotice(p.warnings.length ? `Checked: ${p.warnings.length} thing(s) to look at.` : "Checked: nothing to flag."),
      onError: (e) => setActionError(errorMessage(e, "The check didn't finish.")),
    });
  }

  function confirmRewrite() {
    if (!rewriting) return;
    setRewriteError(null);
    rewrite.mutate(
      { id: rewriting.id, element, instruction: instruction.trim() },
      {
        onSuccess: (p) => {
          setRewriting(null);
          setNotice(p.approval_withdrawn ? "Rewritten. The earlier approval was withdrawn." : "Rewritten.");
        },
        onError: (e) => setRewriteError(errorMessage(e, "Couldn't rewrite that.")),
      },
    );
  }

  const artworkPost = posts.data?.items.find((p) => p.id === artworkId) ?? null;

  const busy = transition.isPending || remove.isPending || duplicate.isPending || check.isPending;

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
                  {post.artwork?.files?.[0]?.url && (
                    <img
                      src={post.artwork.files[0].url ?? undefined}
                      alt={`Artwork for ${post.title}`}
                      className="h-20 w-16 shrink-0 rounded border object-cover"
                      loading="lazy"
                    />
                  )}
                  <div className="min-w-0 flex-1">
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
                {post.content.hashtags.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {post.content.hashtags.map((h) => `#${h}`).join(" ")}
                    {post.generation.hashtag_basis === "ai_suggested" ? " · AI-suggested, not a measured trend" : ""}
                  </p>
                )}
                {post.generation.suggested_time && (
                  <p className="text-xs text-muted-foreground" title={post.generation.suggested_time.evidence}>
                    Suggested time: {formatInZone(post.generation.suggested_time.at, post.generation.suggested_time.timezone)} (a {post.generation.suggested_time.basis} assumption, not measured)
                  </p>
                )}
                {post.generation.last_check && (
                  <p className="text-xs text-muted-foreground">
                    Last checked {formatInZone(post.generation.last_check.checked_at, timeZone)}
                    {Object.entries(post.generation.last_check.cves).map(
                      ([cve, info]) =>
                        ` · ${cve}: ${info.checked ? (info.found ? `in NVD${info.cvss != null ? `, CVSS ${info.cvss}` : ""}${info.kev ? ", known exploited" : ""}` : "NOT in NVD") : "not checked"}`,
                    )}
                  </p>
                )}
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
                {post.external_permalink && (
                  <a className="inline-flex items-center gap-1 text-xs text-primary underline" href={safeHref(post.external_permalink)} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-3 w-3" /> On Instagram
                  </a>
                )}
                {canManage && (
                  <div className="flex flex-wrap gap-2">
                    {["draft", "review", "approved", "cancelled", "failed"].includes(post.status) && post.status !== "cancelled" && (
                      <Button size="sm" variant="outline" onClick={() => openEditor(post)}>
                        <Pencil className="mr-1 h-3.5 w-3.5" /> Edit
                      </Button>
                    )}
                    {["draft", "review", "approved"].includes(post.status) && (
                      <>
                        <Button size="sm" variant="outline" disabled={busy} onClick={() => runCheck(post)}>
                          <ShieldCheck className="mr-1 h-3.5 w-3.5" /> {check.isPending && check.variables === post.id ? "Checking..." : "Check facts & rules"}
                        </Button>
                        <Button size="sm" variant="outline" disabled={busy} onClick={() => setArtworkId(post.id)}>
                          <ImageIcon className="mr-1 h-3.5 w-3.5" /> {post.artwork?.files?.length ? "Artwork" : "Make artwork"}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() => {
                            setRewriting(post);
                            setRewriteError(null);
                            setInstruction("");
                          }}
                        >
                          <Wand2 className="mr-1 h-3.5 w-3.5" /> Rewrite a part
                        </Button>
                      </>
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
                    {["approved", "scheduled"].includes(post.status) && (
                      <Button size="sm" disabled={busy} onClick={() => setScheduleId(post.id)}>
                        <CalendarClock className="mr-1 h-3.5 w-3.5" /> {post.status === "scheduled" ? "Schedule" : "Schedule or publish"}
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

      <ScheduleDialog postId={scheduleId} onOpenChange={(open) => !open && setScheduleId(null)} />

      <ArtworkDialog post={artworkPost} open={artworkId !== null} onOpenChange={(open) => !open && setArtworkId(null)} />

      <Dialog open={rewriting !== null} onOpenChange={(open) => !open && setRewriting(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Rewrite one part with AI</DialogTitle>
            <DialogDescription>Only the part you choose is rewritten. The rest of the post stays as it is.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <select aria-label="Part to rewrite" className={`${NATIVE_SELECT} w-full`} value={element} onChange={(e) => setElement(e.target.value as RewriteElement)}>
              {(Object.keys(REWRITE_LABEL) as RewriteElement[]).map((key) => (
                <option key={key} value={key}>
                  {REWRITE_LABEL[key]}
                </option>
              ))}
            </select>
            <Input aria-label="Instruction" placeholder="Optional: e.g. shorter, friendlier" maxLength={300} value={instruction} onChange={(e) => setInstruction(e.target.value)} />
            {rewriting?.status === "approved" && <p className="text-amber-700">This post is approved. Rewriting it withdraws the approval.</p>}
            {rewriteError && (
              <p role="alert" className="text-destructive">
                {rewriteError}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRewriting(null)}>
              Cancel
            </Button>
            <Button onClick={confirmRewrite} disabled={rewrite.isPending}>
              {rewrite.isPending ? "Rewriting..." : "Rewrite"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
                      <a className="text-primary underline" href={safeHref(s.url)} target="_blank" rel="noopener noreferrer">
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
              {approving.artwork?.files?.length ? (
                <div className="space-y-1 rounded-md border p-3">
                  <p className="font-medium">How it will look in the grid</p>
                  <GridPreview postId={approving.id} compact />
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">This post has no artwork yet, so it isn&apos;t shown in the grid preview.</p>
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

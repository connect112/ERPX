import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Lock, Plus } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/features/institutions/lib/format";
import { type Thread, discussionKeys, discussionsApi } from "@/features/learning/api/learning-api";
import type { TabProps } from "@/features/learning/components/learning-workspace";

const selectClass = "rounded-md border bg-background px-3 py-2 text-sm";

function ThreadView({ courseId, thread, canLock }: { courseId: string; thread: Thread; canLock: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [body, setBody] = useState("");
  const replies = useQuery({ queryKey: discussionKeys.replies(thread.id), queryFn: () => discussionsApi.replies(courseId, thread.id), enabled: open });
  const reply = useMutation({
    mutationFn: () => discussionsApi.reply(courseId, thread.id, body.trim()),
    onSuccess: () => { setBody(""); void queryClient.invalidateQueries({ queryKey: discussionKeys.replies(thread.id) }); },
  });
  const lock = useMutation({ mutationFn: () => discussionsApi.lock(courseId, thread.id, !thread.is_locked), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["learning", "threads"] }) });
  return (
    <div className="rounded-md border p-3" data-testid={`thread-${thread.title}`}>
      <div className="flex items-start justify-between gap-2">
        <button type="button" className="flex flex-1 items-start gap-2 text-left" onClick={() => setOpen((o) => !o)}>
          {open ? <ChevronDown className="mt-0.5 h-4 w-4 text-muted-foreground" /> : <ChevronRight className="mt-0.5 h-4 w-4 text-muted-foreground" />}
          <span>
            <span className="text-sm font-medium">{thread.title}</span>
            <span className="ml-2">
              <Badge variant={thread.internship_id ? "info" : "secondary"}>{thread.internship_id ? "Internship only" : "Course-wide"}</Badge>
              {thread.is_locked && (
                <Badge className="ml-1" variant="warning">
                  <Lock className="mr-1 h-3 w-3" />
                  Locked
                </Badge>
              )}
            </span>
            <span className="block text-xs text-muted-foreground">
              {thread.author_name ?? "Someone"} · {new Date(thread.created_at).toLocaleDateString("en-GB")}
            </span>
          </span>
        </button>
        {canLock && (
          <Button size="sm" variant="outline" disabled={lock.isPending} onClick={() => lock.mutate()}>
            {thread.is_locked ? "Unlock" : "Lock"}
          </Button>
        )}
      </div>
      {open && (
        <div className="mt-3 space-y-3 border-t pt-3">
          <p className="whitespace-pre-wrap text-sm">{thread.body}</p>
          {replies.isLoading ? (
            <Skeleton className="h-8 w-full" />
          ) : (
            <ul className="space-y-2">
              {replies.data?.map((r) => (
                <li key={r.id} className="rounded bg-muted/40 p-2 text-sm">
                  <div className="text-xs text-muted-foreground">{r.author_name ?? "Someone"}</div>
                  <p className="whitespace-pre-wrap">{r.body}</p>
                </li>
              ))}
            </ul>
          )}
          {!thread.is_locked && (
            <div className="space-y-2">
              <Textarea aria-label="Your reply" rows={2} value={body} onChange={(e) => setBody(e.target.value)} placeholder="Write a reply" />
              <Button size="sm" disabled={reply.isPending || !body.trim()} onClick={() => reply.mutate()}>
                Reply
              </Button>
            </div>
          )}
          {(reply.isError || lock.isError) && <p className="text-sm text-destructive">{errorMessage(reply.error ?? lock.error, "That did not work.")}</p>}
        </div>
      )}
    </div>
  );
}

function NewThread({ courseId, internship, canCourse, onClose }: { courseId: string; internship: TabProps["internship"]; canCourse: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [scope, setScope] = useState<"internship" | "course">(internship ? "internship" : "course");
  const create = useMutation({
    mutationFn: () => discussionsApi.create(courseId, { title: title.trim(), body: body.trim(), internship_id: scope === "internship" && internship ? internship.id : null }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["learning", "threads"] }); onClose(); },
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New discussion</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="d-title">Title</Label>
            <Input id="d-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="d-body">Message</Label>
            <Textarea id="d-body" rows={4} value={body} onChange={(e) => setBody(e.target.value)} />
          </div>
          {internship && canCourse && (
            <div className="space-y-1">
              <Label htmlFor="d-scope">Who can see it</Label>
              <select id="d-scope" className={selectClass + " w-full"} value={scope} onChange={(e) => setScope(e.target.value as "internship" | "course")}>
                <option value="internship">Only this internship's students and staff</option>
                <option value="course">Everyone in the course</option>
              </select>
            </div>
          )}
          {create.isError && <p className="text-sm text-destructive">{errorMessage(create.error, "Could not start the discussion.")}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={create.isPending || title.trim().length < 2 || !body.trim()} onClick={() => create.mutate()}>
            Post
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Discussions: course-wide threads as before, plus threads private to one internship (only its students and staff ever see those). */
export function DiscussionsTab({ courseId, internship, needsChoice, ctx }: TabProps) {
  const [creating, setCreating] = useState(false);
  const canCourse = !!ctx.course_caps.discussions_participate;
  const internshipId = internship?.id ?? null;
  const enabled = !!courseId && (canCourse || !!internship);
  const threads = useQuery({ queryKey: discussionKeys.threads(courseId ?? "", internshipId), queryFn: () => discussionsApi.threads(courseId!, internshipId), enabled });
  if (!courseId) return <p className="text-sm text-muted-foreground">Discussions belong to the LMS course; link one to this internship to use them.</p>;
  if (!enabled) return <p className="text-sm text-muted-foreground">{needsChoice ? "Choose an internship above to see its private discussions." : "You do not have access to the discussions."}</p>;
  return (
    <Card data-testid="discussions-tab">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Discussions</CardTitle>
        {!needsChoice || canCourse ? (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" />
            New discussion
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3">
        {needsChoice && <p className="text-sm text-muted-foreground">Showing the course-wide discussions. Choose an internship above to add its private ones.</p>}
        {threads.isLoading && <Skeleton className="h-16 w-full" />}
        {threads.isError && <p className="text-sm text-destructive">Could not load the discussions.</p>}
        {threads.data && threads.data.length === 0 && <p className="text-sm text-muted-foreground">No discussions yet.</p>}
        {threads.data?.map((t) => (
          <ThreadView key={t.id} courseId={courseId} thread={t} canLock={t.internship_id ? !!internship?.can_manage : !!ctx.course_caps.curriculum_manage} />
        ))}
        {creating && <NewThread courseId={courseId} internship={internship} canCourse={canCourse} onClose={() => setCreating(false)} />}
      </CardContent>
    </Card>
  );
}

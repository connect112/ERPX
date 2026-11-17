import { ChevronDown, ChevronRight, Lock } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { type Thread, useCourseLearning, useCreateThread, useReplies, useReply, useThreads } from "@/features/course-learning/api/course-learning-api";
import { errorMessage } from "@/features/my-internship/lib/format";

function ThreadItem({ courseId, thread }: { courseId: string; thread: Thread }) {
  const [open, setOpen] = useState(false);
  const [body, setBody] = useState("");
  const replies = useReplies(courseId, thread.id, open);
  const reply = useReply(courseId, thread.id);
  return (
    <div className="rounded-md border p-3" data-testid={`thread-${thread.title}`}>
      <button type="button" className="flex w-full items-start gap-2 text-left" onClick={() => setOpen((o) => !o)}>
        {open ? <ChevronDown className="mt-0.5 h-4 w-4" /> : <ChevronRight className="mt-0.5 h-4 w-4" />}
        <span>
          <span className="text-sm font-medium">{thread.title}</span>
          {thread.internship_id && <Badge className="ml-2" variant="info">Your internship</Badge>}
          {thread.is_locked && (
            <Badge className="ml-1" variant="warning">
              <Lock className="mr-1 h-3 w-3" />
              Locked
            </Badge>
          )}
          <span className="block text-xs text-muted-foreground">
            {thread.author_name ?? "Someone"} · {new Date(thread.created_at).toLocaleDateString("en-GB")}
          </span>
        </span>
      </button>
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
              <Button size="sm" disabled={reply.isPending || !body.trim()} onClick={() => reply.mutate(body.trim(), { onSuccess: () => setBody("") })}>
                Reply
              </Button>
              {reply.isError && <p className="text-sm text-destructive">{errorMessage(reply.error, "Could not post your reply.")}</p>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** The course discussions a student may see: the course-wide ones, and those private to an internship they hold access on. */
export function CourseDiscussionsPage() {
  const { courseId = "" } = useParams<{ courseId: string }>();
  const course = useCourseLearning(courseId);
  const threads = useThreads(courseId);
  const create = useCreateThread(courseId);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [scope, setScope] = useState("");
  const internships = course.data?.internships ?? [];

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-6">
      <Link to={`/courses/${courseId}`} className="text-sm text-muted-foreground hover:text-foreground">
        ← {course.data?.course_title ?? "Back to the course"}
      </Link>
      <h1 className="text-2xl font-semibold">Discussions</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Start a discussion</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Input aria-label="Title" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Textarea aria-label="Message" rows={3} placeholder="What would you like to ask or share?" value={body} onChange={(e) => setBody(e.target.value)} />
          {internships.length > 0 && (
            <select aria-label="Who can see it" className="rounded-md border bg-background px-3 py-2 text-sm" value={scope} onChange={(e) => setScope(e.target.value)}>
              <option value="">Everyone in the course</option>
              {internships.map((i) => (
                <option key={i.id} value={i.id}>
                  Only my internship: {i.title}
                </option>
              ))}
            </select>
          )}
          {create.isError && <p className="text-sm text-destructive">{errorMessage(create.error, "Could not post.")}</p>}
          <Button
            disabled={create.isPending || title.trim().length < 2 || !body.trim()}
            onClick={() => create.mutate({ title: title.trim(), body: body.trim(), internship_id: scope || null }, { onSuccess: () => { setTitle(""); setBody(""); } })}
          >
            Post
          </Button>
        </CardContent>
      </Card>
      {threads.isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : threads.isError ? (
        <p className="text-sm text-destructive">You do not have access to these discussions.</p>
      ) : (threads.data?.length ?? 0) === 0 ? (
        <p className="text-sm text-muted-foreground">No discussions yet. Be the first to start one.</p>
      ) : (
        <div className="space-y-3">
          {threads.data!.map((t) => (
            <ThreadItem key={t.id} courseId={courseId} thread={t} />
          ))}
        </div>
      )}
    </div>
  );
}

import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronDown, ChevronRight, Lock, Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  useCreateReply,
  useCreateThread,
  useReplies,
  useThreads,
} from "@/features/lms/discussions/api/discussions-hooks";
import {
  type ReplyFormValues,
  type ThreadFormValues,
  replyFormSchema,
  threadFormSchema,
} from "@/features/lms/discussions/schemas/discussion-schemas";

function RepliesSection({ courseId, threadId }: { courseId: string; threadId: string }) {
  const { data: replies, isLoading } = useReplies(courseId, threadId);
  const createReply = useCreateReply(courseId, threadId);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ReplyFormValues>({ resolver: zodResolver(replyFormSchema) });

  const onSubmit = (values: ReplyFormValues) => {
    createReply.mutate(values.body, { onSuccess: () => reset() });
  };

  return (
    <div className="space-y-2 pl-4">
      {isLoading && <Skeleton className="h-8 w-full" />}
      {!isLoading && (replies?.length ?? 0) === 0 && (
        <p className="text-xs text-muted-foreground">No replies yet.</p>
      )}
      {replies?.map((reply) => (
        <div key={reply.id} className="rounded border px-2 py-1.5 text-xs">
          <p>{reply.body}</p>
          <p className="mt-0.5 text-muted-foreground">
            {new Date(reply.created_at).toLocaleString()}
          </p>
        </div>
      ))}
      <form onSubmit={handleSubmit(onSubmit)} className="flex items-start gap-2">
        <div className="flex-1">
          <Textarea rows={2} placeholder="Write a reply..." {...register("body")} />
          {errors.body && <p className="text-sm text-destructive">{errors.body.message}</p>}
        </div>
        <Button type="submit" size="sm" disabled={createReply.isPending}>
          Reply
        </Button>
      </form>
    </div>
  );
}

export function DiscussionsPanel({ courseId }: { courseId: string }) {
  const { data: threads, isLoading } = useThreads(courseId);
  const createThread = useCreateThread(courseId);
  const [formOpen, setFormOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ThreadFormValues>({ resolver: zodResolver(threadFormSchema) });

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onSubmit = (values: ThreadFormValues) => {
    createThread.mutate(values, {
      onSuccess: () => {
        setFormOpen(false);
        reset();
      },
    });
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Discussions</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New thread
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (threads?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No discussion threads yet.</p>
        )}
        {threads?.map((thread) => (
          <div key={thread.id} className="rounded-md border p-3">
            <button
              type="button"
              className="flex w-full items-center gap-2 text-left"
              onClick={() => toggle(thread.id)}
            >
              {expanded.has(thread.id) ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
              <span className="text-sm font-medium">{thread.title}</span>
              {thread.is_locked && <Lock className="h-3 w-3 text-muted-foreground" />}
            </button>
            <p className="mt-1 pl-6 text-xs text-muted-foreground">{thread.body}</p>
            {expanded.has(thread.id) && (
              <div className="mt-3">
                <RepliesSection courseId={courseId} threadId={thread.id} />
              </div>
            )}
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New thread</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="body">Body</Label>
              <Textarea id="body" rows={4} {...register("body")} />
              {errors.body && <p className="text-sm text-destructive">{errors.body.message}</p>}
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createThread.isPending}>
                {createThread.isPending ? "Posting..." : "Post thread"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

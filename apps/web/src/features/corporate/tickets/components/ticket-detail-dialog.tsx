import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import type { SupportTicketPublic } from "@/features/corporate/tickets/api/tickets-api";
import {
  useAddTicketComment,
  useChangeTicketStatus,
  useTicketComments,
} from "@/features/corporate/tickets/api/tickets-hooks";
import {
  type TicketStatus,
  ticketStatusLabels,
  ticketStatusValues,
} from "@/features/corporate/tickets/schemas/ticket-schemas";

interface TicketDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  ticket: SupportTicketPublic | null;
}

export function TicketDetailDialog({ open, onOpenChange, ticket }: TicketDetailDialogProps) {
  const { data: comments, isLoading } = useTicketComments(ticket?.id);
  const changeStatus = useChangeTicketStatus(ticket?.id ?? "");
  const addComment = useAddTicketComment(ticket?.id ?? "");
  const [commentText, setCommentText] = useState("");
  const [isInternal, setIsInternal] = useState(false);

  if (!ticket) return null;

  const handleAddComment = () => {
    if (!commentText.trim()) return;
    addComment.mutate(
      { comment_text: commentText, is_internal: isInternal },
      { onSuccess: () => setCommentText("") }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{ticket.subject}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">{ticket.description}</p>
          <div className="space-y-2">
            <Select
              value={ticket.status}
              onValueChange={(value) => changeStatus.mutate(value as TicketStatus)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ticketStatusValues.map((s) => (
                  <SelectItem key={s} value={s}>
                    {ticketStatusLabels[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Comments
            </p>
            {isLoading && <Skeleton className="h-16 w-full" />}
            {!isLoading && (comments?.length ?? 0) === 0 && (
              <p className="text-sm text-muted-foreground">No comments yet.</p>
            )}
            <div className="max-h-48 space-y-2 overflow-y-auto">
              {comments?.map((comment) => (
                <div key={comment.id} className="rounded-md border p-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">
                      {new Date(comment.created_at).toLocaleString()}
                    </span>
                    {comment.is_internal && <Badge variant="secondary">Internal</Badge>}
                  </div>
                  <p className="mt-1">{comment.comment_text}</p>
                </div>
              ))}
            </div>
            <Textarea
              rows={2}
              placeholder="Add a comment..."
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
            />
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-input"
                checked={isInternal}
                onChange={(e) => setIsInternal(e.target.checked)}
              />
              Internal note
            </label>
            <div className="flex justify-end">
              <Button
                size="sm"
                onClick={handleAddComment}
                disabled={!commentText.trim() || addComment.isPending}
              >
                {addComment.isPending ? "Adding..." : "Add comment"}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

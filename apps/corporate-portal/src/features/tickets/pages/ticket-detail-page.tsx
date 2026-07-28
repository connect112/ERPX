import { useState } from "react";
import { useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useAddComment, useMyTicket, useTicketComments } from "@/features/tickets/api/tickets-hooks";

export function TicketDetailPage() {
  const { ticketId } = useParams<{ ticketId: string }>();
  const { data: ticket, isLoading: ticketLoading } = useMyTicket(ticketId);
  const { data: comments, isLoading: commentsLoading } = useTicketComments(ticketId);
  const addCommentMutation = useAddComment(ticketId as string);
  const [reply, setReply] = useState("");

  const handleReply = () => {
    if (!reply.trim()) return;
    addCommentMutation.mutate(reply, { onSuccess: () => setReply("") });
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        {ticketLoading ? (
          <Skeleton className="h-8 w-80" />
        ) : (
          <h1 className="text-2xl font-semibold">{ticket?.subject}</h1>
        )}
        {ticket && (
          <div className="mt-1 flex items-center gap-2">
            <p className="text-sm text-muted-foreground">{ticket.ticket_number}</p>
            <Badge variant="outline" className="capitalize">
              {ticket.status.replace("_", " ")}
            </Badge>
            <Badge variant="outline" className="capitalize">
              {ticket.priority}
            </Badge>
          </div>
        )}
      </div>

      {ticket && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm">{ticket.description}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Conversation</CardTitle>
          <CardDescription>Replies from you and our support team.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {commentsLoading ? (
            <Skeleton className="h-16 w-full" />
          ) : comments && comments.length > 0 ? (
            <ul className="space-y-3">
              {comments.map((comment) => (
                <li key={comment.id} className="rounded-md bg-muted/50 p-3">
                  <p className="text-sm">{comment.comment_text}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {new Date(comment.created_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No replies yet.</p>
          )}

          <div className="space-y-2 border-t pt-4">
            <Textarea
              rows={3}
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              placeholder="Write a reply..."
            />
            <Button onClick={handleReply} disabled={addCommentMutation.isPending || !reply.trim()}>
              Send reply
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

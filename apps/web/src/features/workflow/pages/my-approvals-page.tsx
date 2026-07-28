import { Check, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  useApproveRequest,
  useMyPendingApprovals,
  useRejectRequest,
} from "@/features/workflow/api/workflow-hooks";

export function MyApprovalsPage() {
  const { data: requests, isLoading, isError } = useMyPendingApprovals();
  const approve = useApproveRequest();
  const reject = useRejectRequest();
  const [comments, setComments] = useState<Record<string, string>>({});

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">My Approvals</h1>
        <p className="mt-1 text-muted-foreground">
          Requests currently waiting on a role you hold.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load your pending approvals. Please try again.
            </p>
          )}

          {!isLoading && !isError && (requests?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Nothing waiting on you right now.
            </p>
          )}

          {!isLoading && !isError && (requests?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Entity type</TableHead>
                  <TableHead>Entity ID</TableHead>
                  <TableHead>Step</TableHead>
                  <TableHead>Comment</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {requests?.map((request) => (
                  <TableRow key={request.id}>
                    <TableCell className="font-mono text-xs">{request.entity_type}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {request.entity_id}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{request.current_step_order}</TableCell>
                    <TableCell className="min-w-[200px]">
                      <Textarea
                        rows={1}
                        placeholder="Optional comment..."
                        value={comments[request.id] ?? ""}
                        onChange={(e) =>
                          setComments((prev) => ({ ...prev, [request.id]: e.target.value }))
                        }
                        className="h-9 min-h-9 text-xs"
                      />
                    </TableCell>
                    <TableCell className="flex justify-end gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label="Approve"
                        disabled={approve.isPending || reject.isPending}
                        onClick={() => approve.mutate({ id: request.id, comment: comments[request.id] })}
                      >
                        <Check className="h-4 w-4 text-emerald-600" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label="Reject"
                        disabled={approve.isPending || reject.isPending}
                        onClick={() => reject.mutate({ id: request.id, comment: comments[request.id] })}
                      >
                        <X className="h-4 w-4 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

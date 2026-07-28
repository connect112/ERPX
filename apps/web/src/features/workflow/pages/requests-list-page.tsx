import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAllRequests } from "@/features/workflow/api/workflow-hooks";
import { RequestStatusBadge } from "@/features/workflow/components/request-status-badge";
import {
  type ApprovalRequestStatus,
  approvalRequestStatusLabels,
  approvalRequestStatusValues,
} from "@/features/workflow/schemas/workflow-schemas";

const PAGE_SIZE = 20;

export function RequestsListPage() {
  const [status, setStatus] = useState<ApprovalRequestStatus | "all">("all");
  const [skip, setSkip] = useState(0);

  const { data, isLoading, isError } = useAllRequests({
    status: status === "all" ? undefined : status,
    skip,
    limit: PAGE_SIZE,
  });

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Approval Requests</h1>
        <p className="mt-1 text-muted-foreground">
          Every approval request submitted across the platform, regardless of who's approving it.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select
            value={status}
            onValueChange={(value) => {
              setStatus(value as ApprovalRequestStatus | "all");
              setSkip(0);
            }}
          >
            <SelectTrigger className="sm:w-56">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {approvalRequestStatusValues.map((s) => (
                <SelectItem key={s} value={s}>
                  {approvalRequestStatusLabels[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load approval requests. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No approval requests found.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Entity type</TableHead>
                  <TableHead>Entity ID</TableHead>
                  <TableHead>Current step</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((request) => (
                  <TableRow key={request.id}>
                    <TableCell className="font-mono text-xs">{request.entity_type}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {request.entity_id}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {request.status === "pending" ? request.current_step_order : "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(request.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <RequestStatusBadge status={request.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} requests)
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip + PAGE_SIZE >= total}
                  onClick={() => setSkip(skip + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

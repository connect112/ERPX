import { useState } from "react";

import { Badge } from "@/components/ui/badge";
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
import { useDownloadDocument } from "@/features/documents/api/documents-hooks";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";
import type { ExpenseClaimStatus } from "@/features/expense-claims/api/expense-claims-api";
import {
  useApproveExpenseClaim,
  useExpenseClaims,
} from "@/features/expense-claims/api/expense-claims-hooks";
import { RejectExpenseClaimDialog } from "@/features/expense-claims/components/reject-expense-claim-dialog";

const PAGE_SIZE = 20;

const statusVariant: Record<ExpenseClaimStatus, "default" | "success" | "destructive"> = {
  pending: "default",
  approved: "success",
  rejected: "destructive",
};

const monthNames = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function formatAmount(value: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(
    value
  );
}

export function ExpenseClaimsPage() {
  const [status, setStatus] = useState<ExpenseClaimStatus | "all">("pending");
  const [skip, setSkip] = useState(0);
  const [rejectTarget, setRejectTarget] = useState<string | null>(null);

  const { data, isLoading, isError } = useExpenseClaims({
    status: status === "all" ? undefined : status,
    skip,
    limit: PAGE_SIZE,
  });
  const { data: employees } = useEmployeesList({ limit: 200 });
  const approveClaim = useApproveExpenseClaim();
  const downloadDocument = useDownloadDocument();

  const employeeName = (id: string) => employees?.items.find((e) => e.id === id)?.full_name ?? id;

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Expense Claims</h1>
        <p className="mt-1 text-muted-foreground">
          Review employee reimbursement claims. Approved claims are added to that month's payslip.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select
            value={status}
            onValueChange={(value) => {
              setStatus(value as ExpenseClaimStatus | "all");
              setSkip(0);
            }}
          >
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="approved">Approved</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
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
              Failed to load expense claims. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No expense claims found for this filter.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Period</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Receipt</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((claim) => (
                  <TableRow key={claim.id}>
                    <TableCell className="font-medium">{employeeName(claim.employee_id)}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {monthNames[claim.period_month - 1]} {claim.period_year}
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-muted-foreground">
                      {claim.description}
                    </TableCell>
                    <TableCell>{formatAmount(claim.amount)}</TableCell>
                    <TableCell>
                      {claim.receipt_document_id ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={downloadDocument.isPending}
                          onClick={() =>
                            downloadDocument.mutate(claim.receipt_document_id as string, {
                              onSuccess: (url) => window.open(url, "_blank"),
                            })
                          }
                        >
                          View
                        </Button>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant[claim.status]} className="capitalize">
                        {claim.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {claim.status === "pending" && (
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => approveClaim.mutate(claim.id)}
                            disabled={approveClaim.isPending}
                          >
                            Approve
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => setRejectTarget(claim.id)}>
                            Reject
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} claims)
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

      <RejectExpenseClaimDialog
        open={!!rejectTarget}
        onOpenChange={(open) => !open && setRejectTarget(null)}
        claimId={rejectTarget}
      />
    </div>
  );
}

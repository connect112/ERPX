import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useVendorsList } from "@/features/accounting/vendors/api/vendors-hooks";
import {
  useApproveExpense,
  useCancelExpense,
  useExpense,
  useRejectExpense,
} from "@/features/accounting/expenses/api/expenses-hooks";
import {
  type ExpenseStatus,
  expenseStatusLabels,
} from "@/features/accounting/expenses/schemas/expense-schemas";

const statusVariant: Record<ExpenseStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  approved: "info",
  partially_paid: "warning",
  paid: "success",
  rejected: "destructive",
  cancelled: "secondary",
};

export function ExpenseDetailPage() {
  const { expenseId } = useParams<{ expenseId: string }>();
  const navigate = useNavigate();
  const { data: expense, isLoading } = useExpense(expenseId);
  const { data: vendors } = useVendorsList({ limit: 200 });
  const approveExpense = useApproveExpense();
  const rejectExpense = useRejectExpense();
  const cancelExpense = useCancelExpense();

  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");

  if (isLoading || !expense) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const vendorName = vendors?.items.find((v) => v.id === expense.vendor_id)?.name ?? expense.vendor_id;

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/accounting/expenses")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{expense.expense_number}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">{vendorName}</span>
              <Badge variant={statusVariant[expense.status]}>
                {expenseStatusLabels[expense.status]}
              </Badge>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          {expense.status === "draft" && (
            <>
              <Button onClick={() => approveExpense.mutate(expense.id)} disabled={approveExpense.isPending}>
                {approveExpense.isPending ? "Approving..." : "Approve"}
              </Button>
              <Button variant="destructive" onClick={() => setRejectOpen(true)}>
                Reject
              </Button>
            </>
          )}
          {expense.status !== "cancelled" && expense.status !== "paid" && expense.status !== "rejected" && (
            <Button
              variant="outline"
              onClick={() => cancelExpense.mutate(expense.id)}
              disabled={cancelExpense.isPending}
            >
              {cancelExpense.isPending ? "Cancelling..." : "Cancel"}
            </Button>
          )}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Expense details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm">
          <p>
            <span className="text-muted-foreground">Category:</span> {expense.category}
          </p>
          <p>
            <span className="text-muted-foreground">Description:</span> {expense.description}
          </p>
          <p>
            <span className="text-muted-foreground">Date:</span>{" "}
            {new Date(expense.expense_date).toLocaleDateString()}
          </p>
          <div className="grid grid-cols-2 gap-2 pt-2">
            <p>
              <span className="text-muted-foreground">Subtotal:</span> ₹{expense.subtotal_amount}
            </p>
            <p>
              <span className="text-muted-foreground">Tax:</span> ₹{expense.tax_amount}
            </p>
            <p className="font-semibold">
              <span className="font-normal text-muted-foreground">Total:</span> ₹{expense.total_amount}
            </p>
            <p>
              <span className="text-muted-foreground">Paid:</span> ₹{expense.amount_paid}
            </p>
          </div>
          {expense.rejection_reason && (
            <p className="pt-2 text-destructive">
              <span className="text-muted-foreground">Rejection reason:</span>{" "}
              {expense.rejection_reason}
            </p>
          )}
          {expense.notes && (
            <div className="pt-2">
              <p className="text-muted-foreground">Notes</p>
              <p className="whitespace-pre-wrap">{expense.notes}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject expense</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="rejectionReason">Reason</Label>
            <Textarea
              id="rejectionReason"
              rows={3}
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={!rejectionReason.trim() || rejectExpense.isPending}
              onClick={() =>
                rejectExpense.mutate(
                  { id: expense.id, rejectionReason },
                  { onSuccess: () => setRejectOpen(false) }
                )
              }
            >
              {rejectExpense.isPending ? "Rejecting..." : "Reject"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

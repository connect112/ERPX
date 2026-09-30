import { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useMyExpenseClaims, useSubmitExpenseClaim } from "@/features/expenses/api/expenses-hooks";
import type { ExpenseClaimStatus } from "@/features/expenses/api/expenses-api";

const statusVariant: Record<ExpenseClaimStatus, "default" | "success" | "destructive"> = {
  pending: "default",
  approved: "success",
  rejected: "destructive",
};

function formatAmount(value: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(
    value
  );
}

export function MyExpensesPage() {
  const { data: claims, isLoading } = useMyExpenseClaims();
  const submitClaim = useSubmitExpenseClaim();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [open, setOpen] = useState(false);
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [receipt, setReceipt] = useState<File | null>(null);

  const resetForm = () => {
    setDescription("");
    setAmount("");
    setReceipt(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const onSubmit = () => {
    const parsedAmount = Number(amount);
    if (!description.trim() || !parsedAmount || parsedAmount <= 0) return;
    submitClaim.mutate(
      { description, amount: parsedAmount, receipt: receipt ?? undefined },
      { onSuccess: () => { setOpen(false); resetForm(); } }
    );
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Expenses</h1>
          <p className="text-sm text-muted-foreground">
            Submit a receipt for reimbursement — approved claims are added to that month's payslip.
          </p>
        </div>
        <Button onClick={() => setOpen(true)}>Submit expense</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">My claims</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : claims && claims.items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Submitted</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Rejection reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {claims.items.map((claim) => (
                  <TableRow key={claim.id}>
                    <TableCell className="text-muted-foreground">
                      {new Date(claim.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="max-w-xs truncate">{claim.description}</TableCell>
                    <TableCell>{formatAmount(claim.amount)}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant[claim.status]} className="capitalize">
                        {claim.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-muted-foreground">
                      {claim.rejection_reason ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              You haven't submitted any expense claims yet.
            </p>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Submit expense</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What was this expense for?"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="amount">Amount</Label>
              <Input
                id="amount"
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="receipt">Receipt</Label>
              <Input
                id="receipt"
                type="file"
                accept="image/*,application/pdf"
                ref={fileInputRef}
                onChange={(e) => setReceipt(e.target.files?.[0] ?? null)}
              />
            </div>
            {submitClaim.isError && (
              <p className="text-sm text-destructive">
                {(submitClaim.error as { response?: { data?: { error?: { message?: string } } } })?.response
                  ?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={onSubmit}
              disabled={submitClaim.isPending || !description.trim() || !amount}
            >
              {submitClaim.isPending ? "Submitting..." : "Submit"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge, type BadgeProps } from "@/components/ui/badge";
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
import { useVendorsList } from "@/features/accounting/vendors/api/vendors-hooks";
import { useExpensesList } from "@/features/accounting/expenses/api/expenses-hooks";
import { ExpenseFormDialog } from "@/features/accounting/expenses/pages/expense-form-dialog";
import {
  type ExpenseStatus,
  expenseStatusLabels,
  expenseStatusValues,
} from "@/features/accounting/expenses/schemas/expense-schemas";

const statusVariant: Record<ExpenseStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  approved: "info",
  partially_paid: "warning",
  paid: "success",
  rejected: "destructive",
  cancelled: "secondary",
};

export function ExpensesListPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<ExpenseStatus | "all">("all");
  const { data: vendors } = useVendorsList({ limit: 200 });
  const { data, isLoading, isError } = useExpensesList({
    status: status === "all" ? undefined : status,
    limit: 100,
  });
  const [formOpen, setFormOpen] = useState(false);

  const vendorName = (id: string) => vendors?.items.find((v) => v.id === id)?.name ?? id;

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Expenses</h1>
          <p className="mt-1 text-muted-foreground">Bills owed to vendors, subject to approval.</p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Expense
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select value={status} onValueChange={(v) => setStatus(v as ExpenseStatus | "all")}>
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {expenseStatusValues.map((s) => (
                <SelectItem key={s} value={s}>
                  {expenseStatusLabels[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load expenses.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">No expenses yet.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Expense #</TableHead>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((expense) => (
                  <TableRow
                    key={expense.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/accounting/expenses/${expense.id}`)}
                  >
                    <TableCell className="font-mono text-xs">{expense.expense_number}</TableCell>
                    <TableCell className="font-medium">{vendorName(expense.vendor_id)}</TableCell>
                    <TableCell className="text-muted-foreground">{expense.category}</TableCell>
                    <TableCell className="text-muted-foreground">₹{expense.total_amount}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant[expense.status]}>
                        {expenseStatusLabels[expense.status]}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ExpenseFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}

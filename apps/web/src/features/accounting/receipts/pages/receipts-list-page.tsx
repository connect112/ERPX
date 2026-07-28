import { Plus } from "lucide-react";
import { useState } from "react";

import { Badge, type BadgeProps } from "@/components/ui/badge";
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
import { useCustomersList } from "@/features/accounting/customers/api/customers-hooks";
import { useReceiptsList, useVoidReceipt } from "@/features/accounting/receipts/api/receipts-hooks";
import { ReceiptFormDialog } from "@/features/accounting/receipts/pages/receipt-form-dialog";
import {
  type ReceiptStatus,
  paymentModeLabels,
  receiptStatusLabels,
} from "@/features/accounting/receipts/schemas/receipt-schemas";

const statusVariant: Record<ReceiptStatus, BadgeProps["variant"]> = {
  cleared: "success",
  voided: "destructive",
};

export function ReceiptsListPage() {
  const { data: customers } = useCustomersList({ limit: 200 });
  const { data, isLoading, isError } = useReceiptsList({ limit: 100 });
  const voidReceipt = useVoidReceipt();
  const [formOpen, setFormOpen] = useState(false);

  const customerName = (id: string) => customers?.items.find((c) => c.id === id)?.name ?? id;

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Receipts</h1>
          <p className="mt-1 text-muted-foreground">Payments received from customers.</p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Receipt
        </Button>
      </div>

      <Card>
        <CardContent className="p-6">
          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load receipts.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">No receipts yet.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Receipt #</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((receipt) => (
                  <TableRow key={receipt.id}>
                    <TableCell className="font-mono text-xs">{receipt.receipt_number}</TableCell>
                    <TableCell className="font-medium">{customerName(receipt.customer_id)}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(receipt.receipt_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">₹{receipt.amount}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {paymentModeLabels[receipt.payment_mode]}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant[receipt.status]}>
                        {receiptStatusLabels[receipt.status]}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {receipt.status === "cleared" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => voidReceipt.mutate(receipt.id)}
                          disabled={voidReceipt.isPending}
                        >
                          Void
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ReceiptFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}

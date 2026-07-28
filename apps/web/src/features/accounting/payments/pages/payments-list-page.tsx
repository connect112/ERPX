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
import { useVendorsList } from "@/features/accounting/vendors/api/vendors-hooks";
import { usePaymentsList, useVoidPayment } from "@/features/accounting/payments/api/payments-hooks";
import { PaymentFormDialog } from "@/features/accounting/payments/pages/payment-form-dialog";
import {
  type PaymentStatus,
  apPaymentModeLabels,
  paymentStatusLabels,
} from "@/features/accounting/payments/schemas/payment-schemas";

const statusVariant: Record<PaymentStatus, BadgeProps["variant"]> = {
  cleared: "success",
  voided: "destructive",
};

export function PaymentsListPage() {
  const { data: vendors } = useVendorsList({ limit: 200 });
  const { data, isLoading, isError } = usePaymentsList({ limit: 100 });
  const voidPayment = useVoidPayment();
  const [formOpen, setFormOpen] = useState(false);

  const vendorName = (id: string) => vendors?.items.find((v) => v.id === id)?.name ?? id;

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Payments</h1>
          <p className="mt-1 text-muted-foreground">Payments made to vendors against approved expenses.</p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Payment
        </Button>
      </div>

      <Card>
        <CardContent className="p-6">
          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load payments.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">No payments yet.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Payment #</TableHead>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Net amount</TableHead>
                  <TableHead>TDS</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((payment) => (
                  <TableRow key={payment.id}>
                    <TableCell className="font-mono text-xs">{payment.payment_number}</TableCell>
                    <TableCell className="font-medium">{vendorName(payment.vendor_id)}</TableCell>
                    <TableCell className="text-muted-foreground">₹{payment.net_amount}</TableCell>
                    <TableCell className="text-muted-foreground">₹{payment.tds_amount}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {apPaymentModeLabels[payment.payment_mode]}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant[payment.status]}>
                        {paymentStatusLabels[payment.status]}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {payment.status === "cleared" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => voidPayment.mutate(payment.id)}
                          disabled={voidPayment.isPending}
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

      <PaymentFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}

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
import { useCustomersList } from "@/features/accounting/customers/api/customers-hooks";
import { useInvoicesList } from "@/features/accounting/invoices/api/invoices-hooks";
import {
  type InvoiceStatus,
  invoiceStatusLabels,
  invoiceStatusValues,
} from "@/features/accounting/invoices/schemas/invoice-schemas";

const statusVariant: Record<InvoiceStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  sent: "info",
  partially_paid: "warning",
  paid: "success",
  overdue: "destructive",
  cancelled: "secondary",
};

export function InvoicesListPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<InvoiceStatus | "all">("all");
  const { data: customers } = useCustomersList({ limit: 200 });
  const { data, isLoading, isError } = useInvoicesList({
    status: status === "all" ? undefined : status,
    limit: 100,
  });

  const customerName = (id: string) => customers?.items.find((c) => c.id === id)?.name ?? id;

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Invoices</h1>
          <p className="mt-1 text-muted-foreground">Sales invoices issued to customers.</p>
        </div>
        <Button onClick={() => navigate("/accounting/invoices/new")}>
          <Plus className="h-4 w-4" />
          New Invoice
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select value={status} onValueChange={(v) => setStatus(v as InvoiceStatus | "all")}>
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {invoiceStatusValues.map((s) => (
                <SelectItem key={s} value={s}>
                  {invoiceStatusLabels[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load invoices.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">No invoices yet.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Invoice #</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Paid</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((invoice) => (
                  <TableRow
                    key={invoice.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/accounting/invoices/${invoice.id}`)}
                  >
                    <TableCell className="font-mono text-xs">{invoice.invoice_number}</TableCell>
                    <TableCell className="font-medium">{customerName(invoice.customer_id)}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(invoice.invoice_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">₹{invoice.total_amount}</TableCell>
                    <TableCell className="text-muted-foreground">₹{invoice.amount_paid}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant[invoice.status]}>
                        {invoiceStatusLabels[invoice.status]}
                      </Badge>
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

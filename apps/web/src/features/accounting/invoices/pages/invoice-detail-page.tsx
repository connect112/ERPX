import { ArrowLeft } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAccountsList } from "@/features/accounting/ledger/api/accounts-hooks";
import { useCustomersList } from "@/features/accounting/customers/api/customers-hooks";
import {
  useCancelInvoice,
  useInvoice,
  usePostInvoice,
} from "@/features/accounting/invoices/api/invoices-hooks";
import {
  type InvoiceStatus,
  invoiceStatusLabels,
} from "@/features/accounting/invoices/schemas/invoice-schemas";

const statusVariant: Record<InvoiceStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  sent: "info",
  partially_paid: "warning",
  paid: "success",
  overdue: "destructive",
  cancelled: "secondary",
};

export function InvoiceDetailPage() {
  const { invoiceId } = useParams<{ invoiceId: string }>();
  const navigate = useNavigate();
  const { data: invoice, isLoading } = useInvoice(invoiceId);
  const { data: customers } = useCustomersList({ limit: 200 });
  const { data: accounts } = useAccountsList({ limit: 500 });
  const postInvoice = usePostInvoice();
  const cancelInvoice = useCancelInvoice();

  if (isLoading || !invoice) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const customerName = customers?.items.find((c) => c.id === invoice.customer_id)?.name ?? invoice.customer_id;
  const accountLabel = (id: string) => {
    const a = accounts?.items.find((x) => x.id === id);
    return a ? `${a.code} — ${a.name}` : id;
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/accounting/invoices")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{invoice.invoice_number}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">{customerName}</span>
              <Badge variant={statusVariant[invoice.status]}>
                {invoiceStatusLabels[invoice.status]}
              </Badge>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          {invoice.status === "draft" && (
            <Button onClick={() => postInvoice.mutate(invoice.id)} disabled={postInvoice.isPending}>
              {postInvoice.isPending ? "Posting..." : "Post invoice"}
            </Button>
          )}
          {invoice.status !== "cancelled" && invoice.status !== "paid" && (
            <Button
              variant="destructive"
              onClick={() => cancelInvoice.mutate(invoice.id)}
              disabled={cancelInvoice.isPending}
            >
              {cancelInvoice.isPending ? "Cancelling..." : "Cancel invoice"}
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Line items</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Description</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead className="text-right">Unit price</TableHead>
                  <TableHead className="text-right">Tax</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoice.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell>{line.description}</TableCell>
                    <TableCell className="text-right">{line.quantity}</TableCell>
                    <TableCell className="text-right">{line.unit_price.toFixed(2)}</TableCell>
                    <TableCell className="text-right">{line.tax_amount.toFixed(2)}</TableCell>
                    <TableCell className="text-right">{line.line_total.toFixed(2)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <div className="flex justify-between border-b py-2">
              <span className="text-muted-foreground">Subtotal</span>
              <span>₹{invoice.subtotal_amount}</span>
            </div>
            <div className="flex justify-between border-b py-2">
              <span className="text-muted-foreground">Tax</span>
              <span>₹{invoice.tax_amount}</span>
            </div>
            <div className="flex justify-between border-b py-2">
              <span className="text-muted-foreground">Discount</span>
              <span>₹{invoice.discount_amount}</span>
            </div>
            <div className="flex justify-between border-b py-2 font-semibold">
              <span>Total</span>
              <span>₹{invoice.total_amount}</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-muted-foreground">Paid</span>
              <span>₹{invoice.amount_paid}</span>
            </div>
            <div className="pt-2 text-xs text-muted-foreground">
              <p>Receivable: {accountLabel(invoice.receivable_account_id)}</p>
              {invoice.tax_payable_account_id && (
                <p>Tax payable: {accountLabel(invoice.tax_payable_account_id)}</p>
              )}
              <p>Due: {new Date(invoice.due_date).toLocaleDateString()}</p>
            </div>
            {invoice.notes && (
              <div className="pt-2">
                <p className="text-muted-foreground">Notes</p>
                <p className="whitespace-pre-wrap">{invoice.notes}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

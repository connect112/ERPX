import { Download, FileText } from "lucide-react";
import { useState } from "react";
import { Link, NavLink } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { type Payment, openFile } from "@/features/pentrix-ops/api/payments-api";
import { PAYMENT_TONE, istDateTime, rupees } from "@/features/pentrix-ops/lib/format";
import { errorMessage } from "@/features/institutions/lib/format";

export function StatusBadge({ payment }: { payment: Pick<Payment, "status" | "status_label"> }) {
  return <Badge variant={PAYMENT_TONE[payment.status] ?? "secondary"}>{payment.status_label}</Badge>;
}

/** Payments and the daily summary are two views of the same money; this switches between them. */
export function PaymentsTabs() {
  const cls = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${isActive ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`;
  return (
    <nav aria-label="Payments views" className="inline-flex gap-1 rounded-md bg-muted p-1">
      <NavLink to="/pentrix-ops/payments" end className={cls}>Payments</NavLink>
      <NavLink to="/pentrix-ops/payments/daily" className={cls}>Daily Summary</NavLink>
    </nav>
  );
}

/** View or save the invoice for a payment that was made. The file is made by the server and fetched with the signed-in session. */
export function InvoiceButtons({ payment }: { payment: Payment }) {
  const [error, setError] = useState<string | null>(null);
  if (!payment.invoice_available) return <span className="text-muted-foreground">—</span>;
  const name = `${payment.invoice_number ?? payment.receipt_number ?? "invoice"}.pdf`;
  const run = (mode: "view" | "save") => {
    setError(null);
    openFile(`/payments/${payment.id}/invoice`, name, mode).catch((e) => setError(errorMessage(e, "Could not open the invoice.")));
  };
  return (
    <div className="flex items-center gap-1">
      <Button size="sm" variant="outline" aria-label={`View invoice ${payment.invoice_number ?? ""}`.trim()} onClick={() => run("view")}>
        <FileText className="h-4 w-4" /> View
      </Button>
      <Button size="sm" variant="outline" aria-label={`Download invoice ${payment.invoice_number ?? ""}`.trim()} onClick={() => run("save")}>
        <Download className="h-4 w-4" /> Download
      </Button>
      {error && <span role="alert" className="text-xs text-destructive">{error}</span>}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b py-2 text-sm last:border-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}

/** Everything known about one transaction, with its invoice and a way to the candidate. */
export function PaymentDialog({ payment, onClose, canOpenCandidate }: { payment: Payment; onClose: () => void; canOpenCandidate: boolean }) {
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Transaction details</DialogTitle>
          <DialogDescription>
            {payment.candidate_name} · <StatusBadge payment={payment} />
          </DialogDescription>
        </DialogHeader>
        <dl>
          <Row label="Amount">{rupees(payment.amount_paise, payment.currency)}</Row>
          <Row label="For">{payment.purpose_label}</Row>
          <Row label="Method">{payment.method}</Row>
          <Row label="Transaction reference"><span className="font-mono text-xs">{payment.reference ?? "—"}</span></Row>
          {payment.provider_order_id && <Row label="Order"><span className="font-mono text-xs">{payment.provider_order_id}</span></Row>}
          <Row label="Started">{payment.created_at ? istDateTime(payment.created_at) : "—"}</Row>
          {payment.paid_at && <Row label="Paid">{istDateTime(payment.paid_at)}</Row>}
          {payment.failed_at && <Row label="Failed">{istDateTime(payment.failed_at)}</Row>}
          {payment.refunded_at && <Row label="Refunded">{istDateTime(payment.refunded_at)}</Row>}
          <Row label="Invoice number"><span className="font-mono text-xs">{payment.invoice_number ?? "—"}</span></Row>
          <Row label="Receipt number"><span className="font-mono text-xs">{payment.receipt_number ?? "—"}</span></Row>
          {payment.provisioning_status && <Row label="Student account">{payment.provisioning_status}</Row>}
        </dl>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <InvoiceButtons payment={payment} />
          {canOpenCandidate && payment.candidate_id && (
            <Button asChild variant="outline" size="sm">
              <Link to={`/pentrix-ops/registrations/${payment.candidate_id}`}>Open candidate</Link>
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

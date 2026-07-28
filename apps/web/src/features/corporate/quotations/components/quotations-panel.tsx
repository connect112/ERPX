import { Plus } from "lucide-react";
import { useState } from "react";

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
import type { QuotationPublic } from "@/features/corporate/quotations/api/quotations-api";
import { useAcceptQuotation, useQuotationsList, useSendQuotation } from "@/features/corporate/quotations/api/quotations-hooks";
import { QuotationFormDialog } from "@/features/corporate/quotations/components/quotation-form-dialog";
import { QuotationStatusBadge } from "@/features/corporate/quotations/components/quotation-status-badge";
import { RejectQuotationDialog } from "@/features/corporate/quotations/components/reject-quotation-dialog";

function QuotationRowActions({
  quotation,
  onReject,
}: {
  quotation: QuotationPublic;
  onReject: (id: string) => void;
}) {
  const sendQuotation = useSendQuotation(quotation.id);
  const acceptQuotation = useAcceptQuotation(quotation.id);

  if (quotation.status === "draft") {
    return (
      <Button
        variant="ghost"
        size="sm"
        onClick={() => sendQuotation.mutate()}
        disabled={sendQuotation.isPending}
      >
        Send
      </Button>
    );
  }
  if (quotation.status === "sent") {
    return (
      <div className="flex justify-end gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => acceptQuotation.mutate()}
          disabled={acceptQuotation.isPending}
        >
          Accept
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onReject(quotation.id)}>
          Reject
        </Button>
      </div>
    );
  }
  return null;
}

export function QuotationsPanel({ clientId }: { clientId: string }) {
  const { data, isLoading } = useQuotationsList({ client_id: clientId, limit: 50 });
  const [formOpen, setFormOpen] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Quotations</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New quotation
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-32 w-full" />}
        {!isLoading && (data?.items.length ?? 0) === 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">No quotations yet.</p>
        )}
        {!isLoading && (data?.items.length ?? 0) > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Number</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Valid until</TableHead>
                <TableHead>Total</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((quotation) => (
                <TableRow key={quotation.id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {quotation.quotation_number}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(quotation.quotation_date).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(quotation.valid_until).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="font-medium">{quotation.total_amount.toLocaleString()}</TableCell>
                  <TableCell>
                    <QuotationStatusBadge status={quotation.status} />
                  </TableCell>
                  <TableCell className="text-right">
                    <QuotationRowActions quotation={quotation} onReject={setRejectTarget} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <QuotationFormDialog open={formOpen} onOpenChange={setFormOpen} clientId={clientId} />
      <RejectQuotationDialog
        open={!!rejectTarget}
        onOpenChange={(open) => !open && setRejectTarget(null)}
        quotationId={rejectTarget}
      />
    </Card>
  );
}

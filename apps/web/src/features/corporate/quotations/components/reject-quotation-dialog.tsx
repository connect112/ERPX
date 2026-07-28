import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useRejectQuotation } from "@/features/corporate/quotations/api/quotations-hooks";

interface RejectQuotationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  quotationId: string | null;
}

export function RejectQuotationDialog({ open, onOpenChange, quotationId }: RejectQuotationDialogProps) {
  const rejectQuotation = useRejectQuotation(quotationId ?? "");
  const [reason, setReason] = useState("");

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) setReason("");
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reject quotation</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="reason">Rejection reason</Label>
          <Textarea id="reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() =>
              rejectQuotation.mutate(reason || undefined, {
                onSuccess: () => {
                  onOpenChange(false);
                  setReason("");
                },
              })
            }
            disabled={rejectQuotation.isPending}
          >
            {rejectQuotation.isPending ? "Rejecting..." : "Reject"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

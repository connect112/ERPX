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
import { useRejectExpenseClaim } from "@/features/expense-claims/api/expense-claims-hooks";

interface RejectExpenseClaimDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  claimId: string | null;
}

export function RejectExpenseClaimDialog({ open, onOpenChange, claimId }: RejectExpenseClaimDialogProps) {
  const rejectClaim = useRejectExpenseClaim();
  const [reason, setReason] = useState("");

  const handleSubmit = () => {
    if (!claimId || !reason) return;
    rejectClaim.mutate(
      { id: claimId, rejectionReason: reason },
      { onSuccess: () => { onOpenChange(false); setReason(""); } }
    );
  };

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
          <DialogTitle>Reject expense claim</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="rejectionReason">Rejection reason</Label>
          <Textarea
            id="rejectionReason"
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>

        {rejectClaim.isError && (
          <p className="text-sm text-destructive">
            {(rejectClaim.error as { response?: { data?: { error?: { message?: string } } } })?.response
              ?.data?.error?.message ?? "Something went wrong. Please try again."}
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleSubmit}
            disabled={!reason || rejectClaim.isPending}
          >
            {rejectClaim.isPending ? "Rejecting..." : "Reject"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

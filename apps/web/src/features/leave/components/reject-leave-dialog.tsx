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
import { useRejectLeave } from "@/features/leave/api/leave-hooks";

interface RejectLeaveDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  applicationId: string | null;
}

export function RejectLeaveDialog({ open, onOpenChange, applicationId }: RejectLeaveDialogProps) {
  const rejectLeave = useRejectLeave();
  const [reason, setReason] = useState("");

  const handleSubmit = () => {
    if (!applicationId || !reason) return;
    rejectLeave.mutate(
      { id: applicationId, rejectionReason: reason },
      {
        onSuccess: () => {
          onOpenChange(false);
          setReason("");
        },
      }
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
          <DialogTitle>Reject leave application</DialogTitle>
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

        {rejectLeave.isError && (
          <p className="text-sm text-destructive">
            {(rejectLeave.error as { response?: { data?: { error?: { message?: string } } } })
              ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleSubmit}
            disabled={!reason || rejectLeave.isPending}
          >
            {rejectLeave.isPending ? "Rejecting..." : "Reject"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

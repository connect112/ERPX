import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useActivateContract } from "@/features/corporate/contracts/api/contracts-hooks";

interface ActivateContractDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  contractId: string | null;
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export function ActivateContractDialog({ open, onOpenChange, contractId }: ActivateContractDialogProps) {
  const activateContract = useActivateContract(contractId ?? "");
  const [signedDate, setSignedDate] = useState(todayIso());

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Activate contract</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="signedDate">Signed date</Label>
          <Input
            id="signedDate"
            type="date"
            value={signedDate}
            onChange={(e) => setSignedDate(e.target.value)}
          />
        </div>

        {activateContract.isError && (
          <p className="text-sm text-destructive">
            {(activateContract.error as { response?: { data?: { error?: { message?: string } } } })
              ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() =>
              activateContract.mutate(signedDate, { onSuccess: () => onOpenChange(false) })
            }
            disabled={activateContract.isPending}
          >
            {activateContract.isPending ? "Activating..." : "Activate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

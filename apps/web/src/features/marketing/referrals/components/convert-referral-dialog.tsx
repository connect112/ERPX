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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useLeadsList } from "@/features/crm/leads/api/leads-hooks";
import { useConvertReferral } from "@/features/marketing/referrals/api/referrals-hooks";

interface ConvertReferralDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  referralId: string | null;
}

export function ConvertReferralDialog({ open, onOpenChange, referralId }: ConvertReferralDialogProps) {
  const convertReferral = useConvertReferral();
  const { data: leads } = useLeadsList({ limit: 200 });
  const [leadId, setLeadId] = useState("");

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) setLeadId("");
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Convert referral</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="leadId">Converted lead</Label>
          <Select value={leadId || undefined} onValueChange={setLeadId}>
            <SelectTrigger id="leadId">
              <SelectValue placeholder="Select lead" />
            </SelectTrigger>
            <SelectContent>
              {leads?.items.map((l) => (
                <SelectItem key={l.id} value={l.id}>
                  {l.full_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {convertReferral.isError && (
          <p className="text-sm text-destructive">
            {(convertReferral.error as { response?: { data?: { error?: { message?: string } } } })
              ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              if (!referralId || !leadId) return;
              convertReferral.mutate(
                { id: referralId, convertedLeadId: leadId },
                {
                  onSuccess: () => {
                    onOpenChange(false);
                    setLeadId("");
                  },
                }
              );
            }}
            disabled={!leadId || convertReferral.isPending}
          >
            {convertReferral.isPending ? "Converting..." : "Convert"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

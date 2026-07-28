import { useEffect, useState } from "react";

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
import { useDisableTwoFactorMutation } from "@/features/auth/api/auth-hooks";

interface TwoFactorDisableDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function TwoFactorDisableDialog({ open, onOpenChange }: TwoFactorDisableDialogProps) {
  const [otpCode, setOtpCode] = useState("");
  const disable = useDisableTwoFactorMutation();

  useEffect(() => {
    if (open) {
      setOtpCode("");
      disable.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const handleDisable = () => {
    disable.mutate(otpCode, {
      onSuccess: () => onOpenChange(false),
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Disable two-factor authentication</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Enter a current code from your authenticator app to confirm you want to disable
            two-factor authentication. This will make your account less secure.
          </p>
          <div className="space-y-2">
            <Label htmlFor="disableOtpCode">Verification code</Label>
            <Input
              id="disableOtpCode"
              inputMode="numeric"
              maxLength={6}
              placeholder="123456"
              value={otpCode}
              onChange={(e) => setOtpCode(e.target.value)}
            />
            {disable.isError && (
              <p className="text-sm text-destructive">Invalid code. Please try again.</p>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={otpCode.length !== 6 || disable.isPending}
            onClick={handleDisable}
          >
            {disable.isPending ? "Disabling..." : "Disable 2FA"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

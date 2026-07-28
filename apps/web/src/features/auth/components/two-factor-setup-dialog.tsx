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
import {
  useConfirmTwoFactorMutation,
  useSetupTwoFactorMutation,
} from "@/features/auth/api/auth-hooks";

interface TwoFactorSetupDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function TwoFactorSetupDialog({ open, onOpenChange }: TwoFactorSetupDialogProps) {
  const [otpCode, setOtpCode] = useState("");
  const setup = useSetupTwoFactorMutation();
  const confirm = useConfirmTwoFactorMutation();

  useEffect(() => {
    if (open) {
      setOtpCode("");
      confirm.reset();
      setup.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const handleConfirm = () => {
    confirm.mutate(otpCode, {
      onSuccess: () => onOpenChange(false),
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Enable two-factor authentication</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {setup.isPending && (
            <p className="text-sm text-muted-foreground">Generating your setup key...</p>
          )}

          {setup.isError && (
            <p className="text-sm text-destructive">
              Could not start two-factor setup. Please try again.
            </p>
          )}

          {setup.data && (
            <>
              <p className="text-sm text-muted-foreground">
                Scan this QR code with an authenticator app (Google Authenticator, Authy, 1Password,
                ...), then enter the 6-digit code it generates to confirm setup.
              </p>
              <div className="flex justify-center">
                <img
                  src={`data:image/png;base64,${setup.data.qr_code_base64}`}
                  alt="Two-factor authentication QR code"
                  className="h-48 w-48 rounded-md border p-2"
                />
              </div>
              <p className="break-all text-center text-xs text-muted-foreground">
                Can't scan it? Enter this key manually: <code>{setup.data.secret}</code>
              </p>

              <div className="space-y-2">
                <Label htmlFor="otpCode">Verification code</Label>
                <Input
                  id="otpCode"
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="123456"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                />
                {confirm.isError && (
                  <p className="text-sm text-destructive">Invalid code. Please try again.</p>
                )}
              </div>
            </>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={!setup.data || otpCode.length !== 6 || confirm.isPending}
            onClick={handleConfirm}
          >
            {confirm.isPending ? "Verifying..." : "Confirm and enable"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { PortalView } from "@/features/internship-onboarding/api";
import { MOBILE_INVALID, MOBILE_NOTICE, displayMobile, normalizeMobile } from "@/features/internship-onboarding/lib/mobile";

interface Props {
  mobile: PortalView["mobile"];
  /** Saves the confirmed number (ten digits). Rejects with the reason, which is shown under the field. */
  onSave: (digits: string) => Promise<void>;
  busy: boolean;
}

/**
 * The student's mobile number for payments. Saving always goes through a confirmation that names the number and says it may be
 * shared with Cashfree; nothing is saved until the student presses Confirm & Save. The server checks the number again.
 */
export function MobileField({ mobile, onSave, busy }: Props) {
  const [value, setValue] = useState(mobile.number ?? "");
  const [problem, setProblem] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const typed = normalizeMobile(value);
  const unchanged = mobile.confirmed && typed !== null && typed === normalizeMobile(mobile.number);

  const ask = () => {
    if (typed === null) {
      setProblem(MOBILE_INVALID);
      return;
    }
    setProblem(null);
    setConfirming(typed);
  };
  const confirm = async () => {
    if (confirming === null) return;
    setSaving(true);
    try {
      await onSave(confirming);
      setValue(confirming);
      setConfirming(null);
    } catch (e) {
      setConfirming(null);
      setProblem(e instanceof Error ? e.message : "The number could not be saved. Please try again.");
    } finally {
      setSaving(false);
    }
  };
  const editAgain = () => {
    setConfirming(null);
    setTimeout(() => input.current?.focus(), 0);
  };

  const status = mobile.confirmed
    ? mobile.record_review_pending
      ? "Saved. This number will be used for your payment. The internship team will review the change to your student record."
      : "Saved. This number will be used for your payment."
    : mobile.valid
      ? "This is the number we have for you. Please check it and confirm it is correct."
      : "We do not have a valid mobile number for you yet. Enter it to pay online.";

  if (!mobile.editable) {
    return (
      <p className="text-sm">
        Mobile number: {mobile.number ?? "none"}
      </p>
    );
  }
  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-2 sm:items-start">
        <div className="space-y-1">
          <Label htmlFor="info-mobile">Mobile number</Label>
          <Input
            id="info-mobile"
            ref={input}
            inputMode="tel"
            autoComplete="tel"
            aria-describedby="info-mobile-notice info-mobile-status"
            aria-invalid={problem !== null}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              setProblem(null);
            }}
          />
          <Button type="button" size="sm" variant="outline" disabled={busy || saving || value.trim() === "" || unchanged} onClick={ask}>
            {mobile.confirmed ? "Update mobile number" : "Save mobile number"}
          </Button>
        </div>
        <p id="info-mobile-notice" className="rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
          {MOBILE_NOTICE}
        </p>
      </div>
      {problem && (
        <p className="text-xs text-destructive" role="alert">
          {problem}
        </p>
      )}
      <p id="info-mobile-status" className="text-xs text-muted-foreground" aria-live="polite">
        {status}
      </p>

      <Dialog open={confirming !== null} onOpenChange={(open) => !open && !saving && editAgain()}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Confirm your mobile number</DialogTitle>
            <DialogDescription className="sr-only">Check the number before it is saved.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <p>
              Mobile number: <strong className="font-mono text-base">{confirming ? displayMobile(confirming) : ""}</strong>
            </p>
            <p>This number may be shared with Cashfree for payment processing. Please verify that it is correct before continuing.</p>
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" disabled={saving} onClick={editAgain}>
              Edit Number
            </Button>
            <Button type="button" disabled={saving} onClick={() => void confirm()}>
              {saving ? "Saving…" : "Confirm & Save"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

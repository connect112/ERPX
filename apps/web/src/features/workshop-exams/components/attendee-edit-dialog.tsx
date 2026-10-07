import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { type Attendee, workshopExamsApi } from "@/features/workshop-exams/api/workshop-exams-api";

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

/** Correct an attendee's name and email. Their personal exam link doesn't change. */
export function AttendeeEditDialog({
  examId,
  attendee,
  onClose,
}: {
  examId: string;
  attendee: Attendee;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(attendee.name);
  const [email, setEmail] = useState(attendee.email);
  const [sendLink, setSendLink] = useState(false);
  const [sendCertificate, setSendCertificate] = useState(false);

  const emailChanged = email.trim().toLowerCase() !== attendee.email.toLowerCase();
  const nameChanged = name.trim().replace(/\s+/g, " ") !== attendee.name;
  const changed = nameChanged || emailChanged;
  const canSendLink = emailChanged && !attendee.certificate_only && !attendee.submitted_at;
  const certificateSent = attendee.certificate_sent_at !== null;
  // A person who has a certificate can have it sent to a corrected address, but only when asked.
  const canSendCertificate = emailChanged && attendee.certificate_number !== null;

  const save = useMutation({
    mutationFn: async () => {
      const saved = await workshopExamsApi.updateAttendee(examId, attendee.id, {
        ...(nameChanged ? { name: name.trim() } : {}),
        ...(emailChanged ? { email: email.trim(), send_link: canSendLink && sendLink } : {}),
      });
      if (canSendCertificate && sendCertificate) await workshopExamsApi.sendCertificate(examId, attendee.id);
      return saved;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });
      onClose();
    },
  });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit {attendee.name}</DialogTitle>
          <DialogDescription>
            Fix a misspelt name or a wrong email address. Their personal exam link stays the same.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (changed && name.trim() && email.trim() && !save.isPending) save.mutate();
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="attendee-name">Name</Label>
            <Input id="attendee-name" value={name} maxLength={255} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="attendee-email">Email</Label>
            <Input id="attendee-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          {canSendLink && (
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-0.5" checked={sendLink} onChange={(e) => setSendLink(e.target.checked)} />
              <span>Email their exam link to the new address</span>
            </label>
          )}
          {canSendCertificate && (
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={sendCertificate}
                onChange={(e) => setSendCertificate(e.target.checked)}
              />
              <span>{certificateSent ? "Send their certificate again to the new address" : "Send their certificate to the new address now"}</span>
            </label>
          )}
          {certificateSent && (
            <p className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
              Their certificate was already emailed. Changing details here does not change or resend it, and the
              verification page will show the new name.
            </p>
          )}
          {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save the changes.")}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!changed || !name.trim() || !email.trim() || save.isPending}>
              {save.isPending ? "Saving..." : "Save changes"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { type WorkshopExam, workshopExamsApi } from "@/features/workshop-exams/api/workshop-exams-api";

function errorMessage(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: { error?: { message?: string; details?: { msg?: string }[] } } } })
    ?.response?.data?.error;
  const detail = Array.isArray(data?.details) ? data?.details[0]?.msg : undefined;
  return (detail ? detail.replace(/^Value error,\s*/, "") : data?.message) ?? fallback;
}

/**
 * Add one student by hand. They are marked "Manual" in the list and get their own exam link like everyone else; or,
 * if they will not sit the exam, they can be given a certificate without it.
 */
export function ManualAttendeeDialog({ exam, onClose }: { exam: WorkshopExam; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [info, setInfo] = useState<Record<string, string>>({});
  const [issueCertificate, setIssueCertificate] = useState(false);

  const add = useMutation({
    mutationFn: () =>
      workshopExamsApi.addManualAttendee(exam.id, {
        name: name.trim(),
        email: email.trim(),
        info,
        issue_certificate: issueCertificate,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });
      onClose();
    },
  });

  const valid = name.trim().length > 0 && /^\S+@\S+\.\S+$/.test(email.trim());

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a student</DialogTitle>
          <DialogDescription>
            Add one person yourself. They appear in the list marked Manual. Whether they sit the exam or not, you can
            review and send their certificate from the list afterwards.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid && !add.isPending) add.mutate();
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="manual-name">Name</Label>
            <Input id="manual-name" value={name} maxLength={255} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="manual-email">Email</Label>
            <Input id="manual-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          {exam.info_fields.map((f) => (
            <div key={f.key} className="space-y-1">
              <Label htmlFor={`manual-${f.key}`}>
                {f.label} <span className="text-xs text-muted-foreground">(optional)</span>
              </Label>
              {f.type === "select" ? (
                <select
                  id={`manual-${f.key}`}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  value={info[f.key] ?? ""}
                  onChange={(e) => setInfo({ ...info, [f.key]: e.target.value })}
                >
                  <option value="">Select...</option>
                  {f.options.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : (
                <Input
                  id={`manual-${f.key}`}
                  type={f.type === "phone" ? "tel" : "text"}
                  value={info[f.key] ?? ""}
                  onChange={(e) => setInfo({ ...info, [f.key]: e.target.value })}
                />
              )}
            </div>
          ))}
          <div className="rounded-md border p-3 text-sm">
            <label htmlFor="manual-issue-certificate" className="flex items-start gap-2 font-medium">
              <input
                id="manual-issue-certificate"
                type="checkbox"
                className="mt-0.5"
                checked={issueCertificate}
                onChange={(e) => setIssueCertificate(e.target.checked)}
              />
              This student will not write the exam; give them a certificate anyway
            </label>
            <p className="mt-1 pl-6 text-xs text-muted-foreground">
              They get no exam link, and their certificate goes out with the others (or when you send it from the list).
              Leave this off if they will sit the exam.
            </p>
          </div>
          {add.isError && <p className="text-sm text-destructive">{errorMessage(add.error, "Could not add the student.")}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!valid || add.isPending}>
              {add.isPending ? "Adding..." : "Add student"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

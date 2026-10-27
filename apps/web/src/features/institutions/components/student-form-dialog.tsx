import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { institutionsApi, institutionsKeys } from "@/features/institutions/api/institutions-api";
import { errorMessage } from "@/features/institutions/lib/format";

export interface StudentFormValue {
  /** Set when editing someone who already exists. */
  id?: string;
  name: string;
  email: string;
  phone: string | null;
  details: Record<string, string>;
}

/**
 * Add a student by hand (to the institution, and to `eventId` when given) or correct an existing one. A correction
 * applies everywhere that person appears, because a student is one record per institution.
 */
export function StudentFormDialog({
  institutionId,
  eventId,
  student,
  onClose,
}: {
  institutionId: string;
  eventId?: string;
  student?: StudentFormValue;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(student?.name ?? "");
  const [email, setEmail] = useState(student?.email ?? "");
  const [phone, setPhone] = useState(student?.phone ?? "");
  const [details, setDetails] = useState<[string, string][]>(Object.entries(student?.details ?? {}));

  const save = useMutation({
    mutationFn: () => {
      const clean = Object.fromEntries(details.map(([k, v]) => [k.trim(), v.trim()] as const).filter(([k, v]) => k && v));
      const payload = { name: name.trim(), email: email.trim(), phone: phone.trim() || null, details: clean };
      return student?.id
        ? institutionsApi.updateStudent(student.id, payload)
        : institutionsApi.addStudent(institutionId, payload, eventId);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: institutionsKeys.all });
      onClose();
    },
  });

  const valid = name.trim().length > 0 && /^\S+@\S+\.\S+$/.test(email.trim());

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{student?.id ? "Edit student" : "Add a student"}</DialogTitle>
          <DialogDescription>
            {student?.id
              ? "Changes apply to this student everywhere they appear at the institution."
              : eventId
                ? "Adds the student to the institution and registers them for this event."
                : "Adds the student to the institution."}
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid && !save.isPending) save.mutate();
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="stu-name">Name</Label>
            <Input id="stu-name" value={name} maxLength={255} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="stu-email">Email</Label>
            <Input id="stu-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="stu-phone">Phone</Label>
            <Input id="stu-phone" type="tel" value={phone} maxLength={50} onChange={(e) => setPhone(e.target.value)} />
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium leading-none">Other details</p>
            {details.map(([key, value], i) => (
              <div key={i} className="flex gap-2">
                <Input aria-label="Detail name" placeholder="e.g. Department" value={key} maxLength={60} onChange={(e) => setDetails(details.map((d, j) => (j === i ? [e.target.value, d[1]] : d)))} />
                <Input aria-label="Detail value" placeholder="e.g. CSE" value={value} maxLength={255} onChange={(e) => setDetails(details.map((d, j) => (j === i ? [d[0], e.target.value] : d)))} />
                <Button type="button" variant="outline" aria-label="Remove detail" onClick={() => setDetails(details.filter((_, j) => j !== i))}>
                  ×
                </Button>
              </div>
            ))}
            {details.length < 30 && (
              <Button type="button" variant="outline" size="sm" onClick={() => setDetails([...details, ["", ""]])}>
                Add a detail
              </Button>
            )}
          </div>
          {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save the student.")}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!valid || save.isPending}>
              {save.isPending ? "Saving..." : student?.id ? "Save changes" : "Add student"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type Institution,
  type InstitutionPayload,
  institutionsApi,
  institutionsKeys,
} from "@/features/institutions/api/institutions-api";
import { errorMessage, formatBytes } from "@/features/institutions/lib/format";

const MOU_ACCEPT = ".pdf,.doc,.docx,.png,.jpg,.jpeg";

/** Create an institution, or edit one. The MOU can be typed in, uploaded as a document, or both. */
export function InstitutionFormDialog({
  institution,
  onClose,
  onSaved,
}: {
  institution?: Institution;
  onClose: () => void;
  onSaved?: (institution: Institution) => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: institution?.name ?? "",
    location: institution?.location ?? "",
    mou_details: institution?.mou_details ?? "",
    faculty_name: institution?.faculty_name ?? "",
    faculty_designation: institution?.faculty_designation ?? "",
    faculty_email: institution?.faculty_email ?? "",
    faculty_phone: institution?.faculty_phone ?? "",
    notes: institution?.notes ?? "",
  });
  const [mouFile, setMouFile] = useState<File | null>(null);
  const [removeMou, setRemoveMou] = useState(false);
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));

  const save = useMutation({
    mutationFn: async () => {
      const payload: InstitutionPayload = {
        name: form.name.trim(),
        location: form.location.trim(),
        faculty_name: form.faculty_name.trim(),
        mou_details: form.mou_details.trim() || null,
        faculty_designation: form.faculty_designation.trim() || null,
        faculty_email: form.faculty_email.trim() || null,
        faculty_phone: form.faculty_phone.trim() || null,
        notes: form.notes.trim() || null,
      };
      let saved = institution ? await institutionsApi.update(institution.id, payload) : await institutionsApi.create(payload);
      if (mouFile) saved = await institutionsApi.uploadMou(saved.id, mouFile);
      else if (removeMou && institution?.mou_filename) saved = await institutionsApi.removeMou(saved.id);
      return saved;
    },
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: institutionsKeys.all });
      onSaved?.(saved);
      onClose();
    },
  });

  const emailOk = !form.faculty_email.trim() || /^\S+@\S+\.\S+$/.test(form.faculty_email.trim());
  const valid = form.name.trim().length >= 2 && form.location.trim().length >= 2 && form.faculty_name.trim().length >= 2 && emailOk;
  const hasMou = !!institution?.mou_filename && !removeMou;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{institution ? "Edit institution" : "New institution"}</DialogTitle>
          <DialogDescription>
            The college or institution we work with, the faculty member who coordinates with us, and the MOU.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid && !save.isPending) save.mutate();
          }}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="inst-name">Institution name</Label>
              <Input id="inst-name" value={form.name} maxLength={255} onChange={(e) => set("name")(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="inst-location">Location (city)</Label>
              <Input id="inst-location" value={form.location} maxLength={255} onChange={(e) => set("location")(e.target.value)} />
            </div>
          </div>

          <fieldset className="space-y-3 rounded-md border p-3">
            <legend className="px-1 text-sm font-medium">Faculty contact</legend>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor="inst-faculty">Name</Label>
                <Input id="inst-faculty" value={form.faculty_name} maxLength={255} onChange={(e) => set("faculty_name")(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="inst-designation">Designation</Label>
                <Input id="inst-designation" value={form.faculty_designation} maxLength={255} onChange={(e) => set("faculty_designation")(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="inst-email">Email</Label>
                <Input id="inst-email" type="email" value={form.faculty_email} onChange={(e) => set("faculty_email")(e.target.value)} />
                {!emailOk && <p className="text-xs text-destructive">That does not look like an email address.</p>}
              </div>
              <div className="space-y-1">
                <Label htmlFor="inst-phone">Phone</Label>
                <Input id="inst-phone" type="tel" value={form.faculty_phone} maxLength={50} onChange={(e) => set("faculty_phone")(e.target.value)} />
              </div>
            </div>
          </fieldset>

          <fieldset className="space-y-3 rounded-md border p-3">
            <legend className="px-1 text-sm font-medium">
              MOU <span className="text-xs font-normal text-muted-foreground">(optional)</span>
            </legend>
            <Textarea
              aria-label="MOU details"
              rows={3}
              placeholder="Signed date, validity, what was agreed..."
              value={form.mou_details}
              onChange={(e) => set("mou_details")(e.target.value)}
            />
            <div className="space-y-1">
              <Label htmlFor="inst-mou-file">MOU document (PDF, Word or image, up to 10 MB)</Label>
              {hasMou && (
                <p className="text-xs text-muted-foreground">
                  Current: {institution?.mou_filename} ({formatBytes(institution?.mou_size_bytes ?? null)}).{" "}
                  <button type="button" className="underline" onClick={() => setRemoveMou(true)}>
                    Remove it
                  </button>
                  {" "}or choose a new one below to replace it.
                </p>
              )}
              {removeMou && <p className="text-xs text-muted-foreground">The document will be removed when you save.</p>}
              <Input
                id="inst-mou-file"
                type="file"
                accept={MOU_ACCEPT}
                onChange={(e) => {
                  setMouFile(e.target.files?.[0] ?? null);
                  setRemoveMou(false);
                }}
              />
            </div>
          </fieldset>

          <div className="space-y-1">
            <Label htmlFor="inst-notes">
              Additional details <span className="text-xs text-muted-foreground">(optional)</span>
            </Label>
            <Textarea id="inst-notes" rows={3} value={form.notes} onChange={(e) => set("notes")(e.target.value)} />
          </div>

          {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save the institution.")}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!valid || save.isPending}>
              {save.isPending ? "Saving..." : institution ? "Save changes" : "Create institution"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

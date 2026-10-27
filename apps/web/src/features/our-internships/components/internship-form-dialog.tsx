import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { institutionsApi, institutionsKeys } from "@/features/institutions/api/institutions-api";
import { errorMessage, formatDateRange } from "@/features/institutions/lib/format";
import {
  type InternshipScope,
  type OurInternship,
  ourInternshipsApi,
  ourInternshipsKeys,
} from "@/features/our-internships/api/our-internships-api";

const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";

/**
 * Start a new internship. The first question is who can be selected: the students of one institution (then, optionally,
 * of just one of its events) or every student registered anywhere.
 */
export function InternshipFormDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (internship: OurInternship) => void }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [scope, setScope] = useState<InternshipScope>("institution");
  const [institutionId, setInstitutionId] = useState("");
  const [eventId, setEventId] = useState("");

  const institutions = useQuery({ queryKey: institutionsKeys.list(""), queryFn: () => institutionsApi.list("") });
  const events = useQuery({
    queryKey: institutionsKeys.events(institutionId),
    queryFn: () => institutionsApi.events(institutionId),
    enabled: scope === "institution" && !!institutionId,
  });

  const create = useMutation({
    mutationFn: () =>
      ourInternshipsApi.create({
        title: title.trim(),
        description: description.trim() || null,
        scope,
        institution_id: scope === "institution" ? institutionId : null,
        event_id: scope === "institution" && eventId ? eventId : null,
      }),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: ourInternshipsKeys.all });
      onCreated(created);
    },
  });

  const valid = title.trim().length >= 2 && (scope === "all" || !!institutionId);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Start a new internship</DialogTitle>
          <DialogDescription>Name it, then choose which students are eligible for selection.</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid && !create.isPending) create.mutate();
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="intern-title">Internship name</Label>
            <Input id="intern-title" value={title} maxLength={255} placeholder="e.g. Pentrix Cyber Internship, Batch 1" onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="intern-description">
              Description <span className="text-xs text-muted-foreground">(optional)</span>
            </Label>
            <Textarea id="intern-description" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>

          <fieldset className="space-y-2 rounded-md border p-3">
            <legend className="px-1 text-sm font-medium">Who can be selected?</legend>
            {(
              [
                ["institution", "Students of a specific institution", "Pick the institution, then the event whose results you want to choose from."],
                ["all", "All students", "Choose from the students of every institution."],
              ] as const
            ).map(([value, label, hint]) => (
              <div key={value} className="flex items-start gap-2 text-sm">
                <input
                  id={`intern-scope-${value}`}
                  type="radio"
                  name="intern-scope"
                  className="mt-1"
                  checked={scope === value}
                  onChange={() => {
                    setScope(value);
                    setEventId("");
                  }}
                />
                <label htmlFor={`intern-scope-${value}`} className="cursor-pointer">
                  <span className="font-medium">{label}</span>
                  <span className="block text-xs text-muted-foreground">{hint}</span>
                </label>
              </div>
            ))}

            {scope === "institution" && (
              <div className="space-y-3 pt-2">
                <div className="space-y-1">
                  <Label htmlFor="intern-institution">Institution</Label>
                  <select
                    id="intern-institution"
                    className={selectClass}
                    value={institutionId}
                    onChange={(e) => {
                      setInstitutionId(e.target.value);
                      setEventId("");
                    }}
                  >
                    <option value="">Choose an institution...</option>
                    {institutions.data?.items.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.name} — {i.location}
                      </option>
                    ))}
                  </select>
                  {institutions.data?.items.length === 0 && (
                    <p className="text-xs text-muted-foreground">There are no institutions yet. Add one under Institutions first.</p>
                  )}
                </div>
                {institutionId && (
                  <div className="space-y-1">
                    <Label htmlFor="intern-event">Event</Label>
                    <select id="intern-event" className={selectClass} value={eventId} onChange={(e) => setEventId(e.target.value)}>
                      <option value="">All events of this institution</option>
                      {events.data?.map((ev) => (
                        <option key={ev.id} value={ev.id}>
                          {ev.name} ({formatDateRange(ev.start_date, ev.end_date)}, {ev.student_count} students)
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            )}
          </fieldset>

          {create.isError && <p className="text-sm text-destructive">{errorMessage(create.error, "Could not create the internship.")}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!valid || create.isPending}>
              {create.isPending ? "Creating..." : "Start internship"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

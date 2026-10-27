import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/features/institutions/lib/format";
import { ourInternshipsKeys, type StudentPerformance } from "@/features/our-internships/api/our-internships-api";
import { type Destination, studentsApi, useDestinations } from "@/features/our-internships/api/students-api";
import { validStudent } from "@/features/our-internships/lib/students";

const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";

/** A single list of the events a student can be added to, grouped by institution. */
export function EventSelect({ destinations, value, onChange, id }: { destinations: Destination[]; value: string; onChange: (eventId: string) => void; id: string }) {
  return (
    <select id={id} aria-label="Event" className={selectClass} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Choose an event...</option>
      {destinations.map((d) => (
        <optgroup key={d.institution_id} label={d.institution_name}>
          {d.events.map((ev) => (
            <option key={ev.id} value={ev.id}>
              {ev.name}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}

/**
 * Add a student to one of the internship's events, or edit one already in its list: their details, and their individual
 * score and remarks for that event (which the selection weighs next to exam marks and the team's score).
 */
export function InternshipStudentDialog({ internshipId, student, onClose }: { internshipId: string; student?: StudentPerformance; onClose: () => void }) {
  const queryClient = useQueryClient();
  const destinations = useDestinations(internshipId);
  const editing = !!student;
  const [eventId, setEventId] = useState(student?.event_id ?? "");
  const [name, setName] = useState(student?.name ?? "");
  const [email, setEmail] = useState(student?.email ?? "");
  const [phone, setPhone] = useState(student?.phone ?? "");
  const [score, setScore] = useState(student?.individual_score !== null && student?.individual_score !== undefined ? String(student.individual_score) : "");
  const [remarks, setRemarks] = useState(student?.remarks ?? "");
  const [notice, setNotice] = useState<string | null>(null);

  // with one possible event there is nothing to choose
  const onlyEvent = destinations.data?.length === 1 && destinations.data[0].events.length === 1 ? destinations.data[0].events[0].id : "";
  const chosen = eventId || onlyEvent;

  const save = useMutation({
    mutationFn: async () => {
      if (student) {
        return studentsApi.update(internshipId, student.student_id, {
          event_id: student.event_id,
          name: name.trim(),
          email: email.trim(),
          phone: phone.trim() || null,
          individual_score: score.trim() === "" ? null : Number(score),
          remarks: remarks.trim() || null,
        });
      }
      return studentsApi.add(internshipId, { event_id: chosen, name: name.trim(), email: email.trim(), phone: phone.trim() || null });
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ourInternshipsKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["institutions"] });
      // someone who was already at the institution is registered rather than created: say so instead of closing silently
      if (!editing && "created" in result && !result.created) {
        setNotice(result.message);
        return;
      }
      onClose();
    },
  });

  const valid = validStudent({ name, email, score, event: editing ? "x" : chosen });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit student" : "Add a student"}</DialogTitle>
          <DialogDescription>
            {editing
              ? "Details apply to this student everywhere at the institution. The score and remarks are for this event."
              : "Adds the student to an event of this internship. Someone already at the institution is reused, not duplicated."}
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid && !save.isPending) save.mutate();
          }}
        >
          {!editing && (
            <div className="space-y-1">
              <Label htmlFor="is-event">Event</Label>
              {destinations.isLoading ? <p className="text-sm text-muted-foreground">Loading...</p> : <EventSelect id="is-event" destinations={destinations.data ?? []} value={chosen} onChange={setEventId} />}
              {destinations.isSuccess && destinations.data.length === 0 && <p className="text-xs text-muted-foreground">There is no event to add students to yet. Create one under Institutions.</p>}
            </div>
          )}
          <div className="space-y-1">
            <Label htmlFor="is-name">Name</Label>
            <Input id="is-name" value={name} maxLength={255} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="is-email">Email</Label>
            <Input id="is-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            {editing && email.trim().toLowerCase() !== student?.email && (
              <p className="text-xs text-amber-700 dark:text-amber-400">Exam marks and hackathon teams are matched by email, so changing it can detach this student from their scores.</p>
            )}
          </div>
          <div className="space-y-1">
            <Label htmlFor="is-phone">Phone</Label>
            <Input id="is-phone" type="tel" value={phone} maxLength={50} onChange={(e) => setPhone(e.target.value)} />
          </div>
          {editing && (
            <>
              <div className="space-y-1">
                <Label htmlFor="is-score">Individual score</Label>
                <Input id="is-score" type="number" min={0} max={9999} step="0.5" className="w-32" value={score} onChange={(e) => setScore(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="is-remarks">Remarks</Label>
                <Textarea id="is-remarks" rows={3} value={remarks} onChange={(e) => setRemarks(e.target.value)} />
              </div>
            </>
          )}
          {notice && <p className="rounded-md border border-sky-300 bg-sky-50 p-3 text-sm text-sky-900 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-200">{notice}</p>}
          {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save the student.")}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              {notice ? "Close" : "Cancel"}
            </Button>
            {!notice && (
              <Button type="submit" disabled={!valid || save.isPending}>
                {save.isPending ? "Saving..." : editing ? "Save changes" : "Add student"}
              </Button>
            )}
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { type PentrixBooking, pentrixApi, pentrixKeys, useStaff } from "@/features/pentrix-ops/api/pentrix-ops-api";
import { OPEN_STATUSES, STATUS_TONE, fromIstInput, istDate, istDateTime, istTime, toIstInput } from "@/features/pentrix-ops/lib/format";
import { errorMessage } from "@/features/institutions/lib/format";
import { selectClass } from "@/features/our-internships/components/letter-fields";

interface Props {
  booking: PentrixBooking;
  /** Administrators can do everything; a team member's own appointment only shows what they may change. */
  mode: "admin" | "mine" | "view";
  onClose: () => void;
}

/** One appointment: its details, and what the person looking at it may do. Every change is carried out in Pentrix, which owns the booking. */
export function BookingDialog({ booking, mode, onClose }: Props) {
  const queryClient = useQueryClient();
  const [current, setCurrent] = useState(booking);
  const [message, setMessage] = useState<string | null>(null);
  const [meeting, setMeeting] = useState(booking.meeting_url ?? "");
  const [notes, setNotes] = useState(booking.notes ?? "");
  const [staffId, setStaffId] = useState(booking.assigned_staff_user_id ?? "");
  const [when, setWhen] = useState(toIstInput(booking.slot_start));
  const [confirmCancel, setConfirmCancel] = useState(false);
  const admin = mode === "admin";
  const readOnly = mode === "view";
  const open = OPEN_STATUSES.includes(current.status);
  const staff = useStaff();
  const slots = useQuery({ queryKey: pentrixKeys.availability, queryFn: pentrixApi.availability, enabled: admin && open, staleTime: 60_000 });

  useEffect(() => {
    setMeeting(current.meeting_url ?? "");
    setNotes(current.notes ?? "");
    setStaffId(current.assigned_staff_user_id ?? "");
  }, [current]);

  const act = useMutation({
    mutationFn: (job: () => Promise<PentrixBooking>) => job(),
    onSuccess: (next) => {
      setCurrent(next);
      setMessage(null);
      void queryClient.invalidateQueries({ queryKey: pentrixKeys.all });
    },
    onError: (error) => setMessage(errorMessage(error, "Could not do that.")),
  });
  const run = (job: () => Promise<PentrixBooking>) => act.mutate(job);
  const busy = act.isPending;

  const progress = admin
    ? (status: string) => run(() => pentrixApi.setStatus(current.id, status))
    : (status: string) => run(() => pentrixApi.myStatus(current.id, status));

  return (
    <Dialog open onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {current.candidate_name || "Candidate"}
            <Badge variant={STATUS_TONE[current.status]}>{current.status_label}</Badge>
          </DialogTitle>
          <DialogDescription>
            {current.candidate_email}
            {current.reference ? ` · ${current.reference}` : ""}
          </DialogDescription>
        </DialogHeader>

        <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Date and time</dt>
            <dd className="font-medium" data-testid="booking-when">{istDateTime(current.slot_start)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Duration</dt>
            <dd>{current.duration_minutes} minutes</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Assigned to</dt>
            <dd>{current.assigned_staff_name ?? "Not assigned yet"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Meeting link</dt>
            <dd>
              {current.meeting_url ? (
                <a className="inline-flex items-center gap-1 text-primary hover:underline" href={current.meeting_url} target="_blank" rel="noopener noreferrer">
                  Open <ExternalLink className="h-3 w-3" aria-hidden="true" />
                </a>
              ) : (
                <span className="text-muted-foreground">None yet</span>
              )}
            </dd>
          </div>
          {current.reschedule_count > 0 && (
            <div>
              <dt className="text-muted-foreground">Rescheduled</dt>
              <dd>{current.reschedule_count} time(s)</dd>
            </div>
          )}
          {current.cancelled_by && (
            <div>
              <dt className="text-muted-foreground">Cancelled by</dt>
              <dd className="capitalize">{current.cancelled_by === "team" ? "the team" : current.cancelled_by}</dd>
            </div>
          )}
        </dl>

        {message && <p role="alert" className="text-sm text-destructive">{message}</p>}

        {open && !readOnly && (
          <section className="space-y-2" aria-label="Progress">
            <h3 className="text-sm font-medium">Progress</h3>
            <div className="flex flex-wrap gap-2">
              {current.status !== "in_progress" && (
                <Button size="sm" variant="outline" disabled={busy} onClick={() => progress("in_progress")}>Mark in progress</Button>
              )}
              <Button size="sm" variant="outline" disabled={busy} onClick={() => progress("completed")}>Mark completed</Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={() => progress("no_show")}>Mark no show</Button>
            </div>
          </section>
        )}

        {admin && open && (
          <>
            <section className="space-y-2" aria-label="Assign">
              <Label htmlFor="pb-staff">Assigned team member</Label>
              <div className="flex gap-2">
                <select id="pb-staff" className={selectClass} value={staffId} onChange={(e) => setStaffId(e.target.value)}>
                  <option value="">Not assigned</option>
                  {staff.data?.map((s) => (
                    <option key={s.id} value={s.id}>{s.full_name}</option>
                  ))}
                </select>
                <Button size="sm" disabled={busy || staffId === (current.assigned_staff_user_id ?? "")} onClick={() => run(() => pentrixApi.assign(current.id, staffId || null))}>
                  Save
                </Button>
              </div>
              {staff.data?.length === 0 && <p className="text-xs text-muted-foreground">No one can be assigned yet. Give a team member the "Pentrix Staff" role first.</p>}
            </section>

            <section className="space-y-2" aria-label="Reschedule">
              <Label htmlFor="pb-when">Move to another time (IST)</Label>
              {slots.data && slots.data.dates.length > 0 && (
                <select
                  aria-label="Choose an open slot"
                  className={selectClass}
                  value=""
                  onChange={(e) => e.target.value && setWhen(toIstInput(e.target.value))}
                >
                  <option value="">Choose an open slot...</option>
                  {slots.data.dates.flatMap((d) =>
                    d.slots.filter((s) => s.available).map((s) => (
                      <option key={s.start} value={s.start}>{istDate(s.start)} · {istTime(s.start)}</option>
                    )),
                  )}
                </select>
              )}
              <div className="flex gap-2">
                <Input id="pb-when" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
                <Button size="sm" disabled={busy || !when || fromIstInput(when) === new Date(current.slot_start).toISOString()} onClick={() => run(() => pentrixApi.reschedule(current.id, fromIstInput(when)))}>
                  Reschedule
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">The team can move an appointment to any free slot, even inside the candidate's own cut-off.</p>
            </section>

            <section className="space-y-2" aria-label="Meeting link">
              <Label htmlFor="pb-meeting">Meeting link</Label>
              <div className="flex gap-2">
                <Input id="pb-meeting" value={meeting} placeholder="https://..." onChange={(e) => setMeeting(e.target.value)} />
                <Button size="sm" disabled={busy || meeting === (current.meeting_url ?? "")} onClick={() => run(() => pentrixApi.setMeeting(current.id, meeting.trim() || null))}>
                  Save
                </Button>
              </div>
            </section>
          </>
        )}

        <section className="space-y-2" aria-label="Notes">
          <Label htmlFor="pb-notes">Notes (the candidate never sees these)</Label>
          <Textarea id="pb-notes" rows={3} value={notes} maxLength={4000} readOnly={readOnly} onChange={(e) => setNotes(e.target.value)} />
          {!readOnly && (
            <Button
              size="sm"
              variant="outline"
              disabled={busy || notes === (current.notes ?? "")}
              onClick={() => run(() => (admin ? pentrixApi.setNotes(current.id, notes.trim() || null) : pentrixApi.myNotes(current.id, notes.trim() || null)))}
            >
              Save notes
            </Button>
          )}
        </section>

        {admin && open && (
          <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3">
            {confirmCancel ? (
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span>Cancel this appointment? The candidate will see it as cancelled and the slot is freed.</span>
                <Button size="sm" variant="destructive" disabled={busy} onClick={() => run(() => pentrixApi.cancel(current.id))}>Yes, cancel it</Button>
                <Button size="sm" variant="outline" onClick={() => setConfirmCancel(false)}>Keep it</Button>
              </div>
            ) : (
              <Button size="sm" variant="outline" className="text-destructive" onClick={() => setConfirmCancel(true)}>Cancel appointment</Button>
            )}
            <Button size="sm" variant="ghost" onClick={onClose}>Close</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

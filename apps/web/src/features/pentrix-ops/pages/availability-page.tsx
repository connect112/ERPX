import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { type AvailabilitySettings, type HoursWindow, type StaffHours, pentrixApi, pentrixKeys } from "@/features/pentrix-ops/api/pentrix-ops-api";
import { fromIstInput, istDateTime, usePentrixPermissions } from "@/features/pentrix-ops/lib/format";
import { errorMessage } from "@/features/institutions/lib/format";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function NumberField({ id, label, value, onChange, disabled, hint }: { id: string; label: string; value: number; onChange: (n: number) => void; disabled: boolean; hint?: string }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type="number" min={0} value={value} disabled={disabled} onChange={(e) => onChange(Number(e.target.value))} />
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function hoursInWords(windows: HoursWindow[]): string {
  return windows.map((w) => `${DAYS[w.weekday]} ${w.start}–${w.end}`).join(", ");
}

function HoursDialog({ member, onClose }: { member: StaffHours; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [windows, setWindows] = useState<HoursWindow[]>(member.windows);
  const save = useMutation({
    mutationFn: () => pentrixApi.setStaffHours(member.user_id, windows),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: pentrixKeys.staffHours });
      onClose();
    },
  });
  const change = (index: number, patch: Partial<HoursWindow>) => setWindows((all) => all.map((w, i) => (i === index ? { ...w, ...patch } : w)));
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Hours for {member.full_name}</DialogTitle>
          <DialogDescription>
            Times are India Standard Time. With no windows, {member.full_name} can be given any appointment the booking hours allow. With windows, only appointments that fit
            completely inside one.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          {windows.length === 0 && <p className="rounded-md border p-3 text-sm text-muted-foreground">No windows: available whenever the booking hours allow.</p>}
          {windows.map((w, i) => (
            <div key={i} className="flex flex-wrap items-end gap-2">
              <div className="space-y-1">
                <Label htmlFor={`hw-day-${i}`}>Day</Label>
                <select id={`hw-day-${i}`} className="h-10 rounded-md border bg-background px-3 text-sm" value={w.weekday} onChange={(e) => change(i, { weekday: Number(e.target.value) })}>
                  {WEEKDAYS.map((d, n) => <option key={d} value={n}>{d}</option>)}
                </select>
              </div>
              <div className="space-y-1"><Label htmlFor={`hw-from-${i}`}>From</Label><Input id={`hw-from-${i}`} type="time" className="w-32" value={w.start} onChange={(e) => change(i, { start: e.target.value })} /></div>
              <div className="space-y-1"><Label htmlFor={`hw-to-${i}`}>To</Label><Input id={`hw-to-${i}`} type="time" className="w-32" value={w.end} onChange={(e) => change(i, { end: e.target.value })} /></div>
              <Button type="button" variant="ghost" size="icon" aria-label={`Remove window ${i + 1}`} onClick={() => setWindows((all) => all.filter((_, n) => n !== i))}><Trash2 className="h-4 w-4" /></Button>
            </div>
          ))}
          <Button type="button" variant="outline" size="sm" onClick={() => setWindows((all) => [...all, { weekday: 0, start: "18:00", end: "21:00" }])}>Add a window</Button>
          {save.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(save.error, "Could not save the hours.")}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save hours"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** When each team member who takes Pentrix appointments is available. ERPX checks it when an appointment is assigned or moved. */
function TeamHoursCard({ canManage }: { canManage: boolean }) {
  const team = useQuery({ queryKey: pentrixKeys.staffHours, queryFn: pentrixApi.staffHours });
  const [editing, setEditing] = useState<StaffHours | null>(null);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Team availability</CardTitle>
        <CardDescription>When each team member can take appointments (India time). Someone with no hours set can take any appointment the booking hours allow.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {team.isLoading && <Skeleton className="h-16" />}
        {team.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(team.error, "Could not load the team.")}</p>}
        {team.data && team.data.length === 0 && <p className="text-sm text-muted-foreground">Nobody has been given the Pentrix Staff role yet.</p>}
        {team.data?.map((m) => (
          <div key={m.user_id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3">
            <div>
              <div className="font-medium">{m.full_name}</div>
              <div className="text-sm text-muted-foreground">{m.restricted ? hoursInWords(m.windows) : "Any time the booking hours allow"}</div>
            </div>
            {canManage && <Button size="sm" variant="outline" aria-label={`Set hours for ${m.full_name}`} onClick={() => setEditing(m)}>Set hours</Button>}
          </div>
        ))}
      </CardContent>
      {editing && <HoursDialog key={editing.user_id} member={editing} onClose={() => setEditing(null)} />}
    </Card>
  );
}

/** When candidates can book, and the rules for changing or cancelling. Pentrix applies these the moment they are saved. */
export function AvailabilityPage() {
  const perms = usePentrixPermissions();
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: pentrixKeys.settings, queryFn: pentrixApi.settings });
  const closed = useQuery({ queryKey: pentrixKeys.closed, queryFn: pentrixApi.closed });
  const [form, setForm] = useState<AvailabilitySettings | null>(null);
  const [saved, setSaved] = useState(false);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (settings.data) setForm(settings.data);
  }, [settings.data]);

  const save = useMutation({
    mutationFn: (changes: Partial<AvailabilitySettings>) => pentrixApi.saveSettings(changes),
    onSuccess: (next) => {
      setForm(next);
      setSaved(true);
      void queryClient.invalidateQueries({ queryKey: pentrixKeys.all });
    },
  });
  const addClosed = useMutation({
    mutationFn: () => pentrixApi.addClosed(fromIstInput(from), fromIstInput(to), reason),
    onSuccess: () => {
      setFrom("");
      setTo("");
      setReason("");
      void queryClient.invalidateQueries({ queryKey: pentrixKeys.closed });
    },
  });
  const removeClosed = useMutation({ mutationFn: (id: string) => pentrixApi.removeClosed(id), onSuccess: () => void queryClient.invalidateQueries({ queryKey: pentrixKeys.closed }) });

  const readOnly = !perms.canManage;
  const set = <K extends keyof AvailabilitySettings>(key: K, value: AvailabilitySettings[K]) => {
    setSaved(false);
    setForm((f) => (f ? { ...f, [key]: value } : f));
  };

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Booking Settings</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          When candidates can book Pentrix appointments, how long they are, how many people a slot takes, and when a candidate can still change or cancel. Times are in India
          Standard Time (6:00 PM to 9:00 PM is the default). Appointments that are already booked are not moved by changing these.
        </p>
      </div>
      {settings.isLoading && <Skeleton className="h-64" />}
      {settings.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(settings.error, "Could not load the settings from Pentrix.")}</p>}

      {form && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Availability</CardTitle>
            <CardDescription>Time zone: {form.timezone}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <fieldset className="space-y-2" disabled={readOnly}>
              <legend className="text-sm font-medium">Working days</legend>
              <div className="flex flex-wrap gap-2">
                {DAYS.map((name, day) => {
                  const on = form.working_days.includes(day);
                  return (
                    <Button
                      key={name}
                      type="button"
                      size="sm"
                      variant={on ? "default" : "outline"}
                      aria-pressed={on}
                      onClick={() => set("working_days", on ? form.working_days.filter((d) => d !== day) : [...form.working_days, day].sort())}
                    >
                      {name}
                    </Button>
                  );
                })}
              </div>
            </fieldset>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor="av-start">First slot starts</Label>
                <Input id="av-start" type="time" value={form.start_time} disabled={readOnly} onChange={(e) => set("start_time", e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="av-end">Last slot ends</Label>
                <Input id="av-end" type="time" value={form.end_time} disabled={readOnly} onChange={(e) => set("end_time", e.target.value)} />
              </div>
              <NumberField id="av-slot" label="Slot length (minutes)" value={form.slot_minutes} disabled={readOnly} onChange={(n) => set("slot_minutes", n)} />
              <NumberField id="av-cap" label="People per slot" value={form.capacity} disabled={readOnly} onChange={(n) => set("capacity", n)} hint="1 = one candidate per slot." />
              <NumberField id="av-ahead" label="Bookable days ahead" value={form.advance_days} disabled={readOnly} onChange={(n) => set("advance_days", n)} />
              <NumberField id="av-notice" label="Minimum notice (minutes)" value={form.min_notice_minutes} disabled={readOnly} onChange={(n) => set("min_notice_minutes", n)} />
              <div className="space-y-1.5">
                <Label htmlFor="av-from">Available from (optional)</Label>
                <Input id="av-from" type="date" value={form.available_from ?? ""} disabled={readOnly} onChange={(e) => set("available_from", e.target.value || null)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="av-until">Available until (optional)</Label>
                <Input id="av-until" type="date" value={form.available_until ?? ""} disabled={readOnly} onChange={(e) => set("available_until", e.target.value || null)} />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <NumberField id="av-cutoff" label="Change/cancel cut-off (minutes before)" value={form.cancel_cutoff_minutes} disabled={readOnly} onChange={(n) => set("cancel_cutoff_minutes", n)} hint="A candidate cannot cancel or reschedule inside this." />
              <NumberField id="av-resched" label="Reschedules allowed" value={form.max_reschedules} disabled={readOnly} onChange={(n) => set("max_reschedules", n)} />
              <div className="space-y-1.5 sm:col-span-3">
                <Label htmlFor="av-meet">Meeting link for new bookings (optional)</Label>
                <Input id="av-meet" value={form.meeting_url_template} placeholder="https://meet.example.com/pentrix-{ref}" disabled={readOnly} onChange={(e) => set("meeting_url_template", e.target.value)} />
                <p className="text-xs text-muted-foreground">{"{ref}"} becomes the booking's reference, so each appointment gets its own link. Leave empty to add links by hand.</p>
              </div>
            </div>
            {save.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(save.error, "Pentrix did not accept those settings.")}</p>}
            {saved && <p role="status" className="text-sm text-emerald-700 dark:text-emerald-400">Saved. Candidates see the new availability now.</p>}
            <Button disabled={readOnly || save.isPending} onClick={() => save.mutate(form)}>{save.isPending ? "Saving..." : "Save settings"}</Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Closed periods</CardTitle>
          <CardDescription>Holidays, events or days the team is away. Nobody can book inside these.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {closed.data?.length === 0 && <p className="text-sm text-muted-foreground">No closed periods.</p>}
          <ul className="space-y-2" aria-label="Closed periods">
            {closed.data?.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-3 rounded-md border p-3 text-sm">
                <span>
                  <strong>{c.reason || "Closed"}</strong>
                  <span className="ml-2 text-muted-foreground">{istDateTime(c.start_at)} to {istDateTime(c.end_at)}</span>
                </span>
                <Button size="icon" variant="ghost" aria-label={`Remove ${c.reason || "closed period"}`} disabled={readOnly} onClick={() => removeClosed.mutate(c.id)}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </li>
            ))}
          </ul>
          {!readOnly && (
            <form
              className="grid gap-3 sm:grid-cols-4"
              onSubmit={(e) => {
                e.preventDefault();
                addClosed.mutate();
              }}
            >
              <div className="space-y-1">
                <Label htmlFor="cp-from">From (IST)</Label>
                <Input id="cp-from" type="datetime-local" required value={from} onChange={(e) => setFrom(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="cp-to">To (IST)</Label>
                <Input id="cp-to" type="datetime-local" required value={to} onChange={(e) => setTo(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="cp-reason">Reason</Label>
                <Input id="cp-reason" value={reason} maxLength={200} placeholder="Diwali" onChange={(e) => setReason(e.target.value)} />
              </div>
              <div className="flex items-end">
                <Button type="submit" disabled={addClosed.isPending || !from || !to}>Add closed period</Button>
              </div>
              {addClosed.isError && <p role="alert" className="text-sm text-destructive sm:col-span-4">{errorMessage(addClosed.error, "Could not add that.")}</p>}
            </form>
          )}
        </CardContent>
      </Card>
      <TeamHoursCard canManage={perms.canManage} />
    </div>
  );
}

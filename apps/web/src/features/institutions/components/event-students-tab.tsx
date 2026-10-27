import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Pencil, Upload, UserMinus, UserPlus, Users } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type EventStudent,
  type InstitutionEvent,
  institutionsApi,
  institutionsKeys,
} from "@/features/institutions/api/institutions-api";
import { StudentFormDialog } from "@/features/institutions/components/student-form-dialog";
import { StudentImportDialog } from "@/features/institutions/components/student-import-dialog";
import { errorMessage } from "@/features/institutions/lib/format";
import { useDebounced } from "@/features/institutions/lib/use-debounced";

/**
 * The students registered for one event. Their individual score and remarks are edited here (saved when you leave the
 * box) and are what the internship selection later uses alongside exam marks and the team's hackathon score.
 */
export function EventStudentsTab({ event }: { event: InstitutionEvent }) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [importing, setImporting] = useState(false);
  const [adding, setAdding] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [editing, setEditing] = useState<EventStudent | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const q = useDebounced(search.trim());

  const students = useQuery({ queryKey: institutionsKeys.eventStudents(event.id, q), queryFn: () => institutionsApi.eventStudents(event.id, q) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: institutionsKeys.all });

  const unregister = useMutation({ mutationFn: (studentId: string) => institutionsApi.unregister(event.id, studentId), onSuccess: refresh });
  const save = useMutation({
    mutationFn: (v: { studentId: string; individual_score?: number | null; remarks?: string | null }) =>
      institutionsApi.updateRegistration(event.id, v.studentId, { individual_score: v.individual_score, remarks: v.remarks }),
    onSuccess: refresh,
  });

  const fetchLinked = useMutation({
    mutationFn: () => institutionsApi.syncEventStudents(event.id),
    onSuccess: (result) => {
      setNotice(result.message);
      void refresh();
    },
  });

  const full = event.max_capacity !== null && event.student_count >= event.max_capacity;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Input aria-label="Search students" placeholder="Search name, email or phone" className="w-72" value={search} onChange={(e) => setSearch(e.target.value)} />
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={fetchLinked.isPending} onClick={() => fetchLinked.mutate()}>
            <Download className="h-4 w-4" />
            {fetchLinked.isPending ? "Fetching..." : "Fetch from exams & hackathons"}
          </Button>
          <Button variant="outline" onClick={() => setRegistering(true)}>
            <Users className="h-4 w-4" />
            Register existing
          </Button>
          <Button variant="outline" onClick={() => setImporting(true)}>
            <Upload className="h-4 w-4" />
            Import list
          </Button>
          <Button onClick={() => setAdding(true)} disabled={full}>
            <UserPlus className="h-4 w-4" />
            Add student
          </Button>
        </div>
      </div>
      {notice && <p className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200">{notice}</p>}
      {fetchLinked.isError && <p className="text-sm text-destructive">{errorMessage(fetchLinked.error, "Could not fetch the students.")}</p>}
      {full && <p className="text-sm text-muted-foreground">This event is full ({event.max_capacity} students). Raise its capacity to register more.</p>}

      <Card>
        <CardContent className="p-0">
          {students.isLoading ? (
            <div className="space-y-2 p-6">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : students.isError ? (
            <p className="p-6 text-sm text-destructive">Could not load students.</p>
          ) : (students.data?.items.length ?? 0) === 0 ? (
            <p className="p-8 text-center text-sm text-muted-foreground">
              {q ? "No student matches." : "No students registered for this event yet. Import the registration list."}
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead className="w-28">Individual score</TableHead>
                  <TableHead>Remarks</TableHead>
                  <TableHead className="w-24" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {students.data?.items.map((s) => (
                  <TableRow key={s.student_id}>
                    <TableCell className="font-medium">
                      {s.name}
                      {Object.keys(s.details).length > 0 && (
                        <span className="block text-xs font-normal text-muted-foreground">
                          {Object.entries(s.details)
                            .map(([k, v]) => `${k}: ${v}`)
                            .join(" · ")}
                        </span>
                      )}
                    </TableCell>
                    <TableCell>{s.email}</TableCell>
                    <TableCell>{s.phone ?? "—"}</TableCell>
                    <TableCell>
                      <ScoreBox student={s} onSave={(value) => save.mutate({ studentId: s.student_id, individual_score: value })} />
                    </TableCell>
                    <TableCell>
                      <RemarksBox student={s} onSave={(value) => save.mutate({ studentId: s.student_id, remarks: value })} />
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" aria-label={`Edit ${s.name}`} onClick={() => setEditing(s)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Remove ${s.name} from this event`}
                          onClick={() => {
                            if (window.confirm(`Remove ${s.name} from this event? They stay at the institution and in their other events.`)) unregister.mutate(s.student_id);
                          }}
                        >
                          <UserMinus className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      {students.data && (
        <p className="text-xs text-muted-foreground">
          {students.data.total} registered{event.max_capacity ? ` of ${event.max_capacity}` : ""}
        </p>
      )}
      {(save.isError || unregister.isError) && (
        <p className="text-sm text-destructive">{errorMessage(save.error ?? unregister.error, "Could not save that change.")}</p>
      )}

      {importing && <StudentImportDialog institutionId={event.institution_id} eventId={event.id} eventName={event.name} onClose={() => setImporting(false)} />}
      {adding && <StudentFormDialog institutionId={event.institution_id} eventId={event.id} onClose={() => setAdding(false)} />}
      {editing && (
        <StudentFormDialog
          institutionId={event.institution_id}
          student={{ id: editing.student_id, name: editing.name, email: editing.email, phone: editing.phone, details: editing.details }}
          onClose={() => setEditing(null)}
        />
      )}
      {registering && <RegisterExistingDialog event={event} onClose={() => setRegistering(false)} />}
    </div>
  );
}

function ScoreBox({ student, onSave }: { student: EventStudent; onSave: (value: number | null) => void }) {
  const [value, setValue] = useState(student.individual_score === null ? "" : String(student.individual_score));
  return (
    <Input
      aria-label={`Individual score for ${student.name}`}
      inputMode="decimal"
      className="h-8 w-24"
      value={value}
      onChange={(e) => setValue(e.target.value.replace(/[^\d.]/g, ""))}
      onBlur={() => {
        const next = value.trim() === "" ? null : Number(value);
        if (next !== null && !Number.isFinite(next)) return setValue(student.individual_score === null ? "" : String(student.individual_score));
        if (next !== student.individual_score) onSave(next);
      }}
    />
  );
}

function RemarksBox({ student, onSave }: { student: EventStudent; onSave: (value: string | null) => void }) {
  const [value, setValue] = useState(student.remarks ?? "");
  return (
    <Input
      aria-label={`Remarks for ${student.name}`}
      className="h-8 min-w-[12rem]"
      maxLength={5000}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => {
        const next = value.trim() || null;
        if (next !== (student.remarks ?? null)) onSave(next);
      }}
    />
  );
}

/** Pick students who are already at the institution (from another event or an earlier list) to register for this one. */
function RegisterExistingDialog({ event, onClose }: { event: InstitutionEvent; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const q = useDebounced(search.trim());

  const all = useQuery({
    queryKey: institutionsKeys.students(event.institution_id, q),
    queryFn: () => institutionsApi.students(event.institution_id, q),
  });
  const candidates = useMemo(() => (all.data?.items ?? []).filter((s) => !s.events.some((e) => e.event_id === event.id)), [all.data, event.id]);

  const register = useMutation({
    mutationFn: () => institutionsApi.registerStudents(event.id, [...picked]),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: institutionsKeys.all });
      onClose();
    },
  });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Register existing students</DialogTitle>
          <DialogDescription>Students already at this institution who are not yet in {event.name}.</DialogDescription>
        </DialogHeader>
        <Input aria-label="Search students" placeholder="Search name or email" value={search} onChange={(e) => setSearch(e.target.value)} />
        <div className="max-h-72 space-y-1 overflow-y-auto rounded-md border p-2">
          {all.isLoading && <Skeleton className="h-8 w-full" />}
          {!all.isLoading && candidates.length === 0 && <p className="p-3 text-center text-sm text-muted-foreground">No one to add.</p>}
          {candidates.map((s) => (
            <label key={s.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-muted">
              <input
                type="checkbox"
                checked={picked.has(s.id)}
                onChange={(e) => {
                  const next = new Set(picked);
                  if (e.target.checked) next.add(s.id);
                  else next.delete(s.id);
                  setPicked(next);
                }}
              />
              <span className="font-medium">{s.name}</span>
              <span className="text-muted-foreground">{s.email}</span>
            </label>
          ))}
        </div>
        {register.isError && <p className="text-sm text-destructive">{errorMessage(register.error, "Could not register them.")}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={picked.size === 0 || register.isPending} onClick={() => register.mutate()}>
            {register.isPending ? "Registering..." : `Register ${picked.size || ""}`.trim()}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

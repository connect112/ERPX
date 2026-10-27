import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Upload, UserPlus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { StudentImportDialog } from "@/features/institutions/components/student-import-dialog";
import { errorMessage } from "@/features/institutions/lib/format";
import { ourInternshipsKeys, type StudentPerformance } from "@/features/our-internships/api/our-internships-api";
import { studentsApi, useDestinations } from "@/features/our-internships/api/students-api";
import { EventSelect, InternshipStudentDialog } from "@/features/our-internships/components/internship-student-dialog";
import { StudentWiseView } from "@/features/our-internships/components/student-wise-view";

function ImportFlow({ internshipId, onClose }: { internshipId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const destinations = useDestinations(internshipId);
  const [eventId, setEventId] = useState("");
  const [started, setStarted] = useState(false);
  const all = (destinations.data ?? []).flatMap((d) => d.events.map((e) => ({ ...e, institution_id: d.institution_id })));
  const chosen = eventId || (all.length === 1 ? all[0].id : "");
  const event = all.find((e) => e.id === chosen);

  if (started && event) {
    return (
      <StudentImportDialog
        institutionId={event.institution_id}
        eventId={event.id}
        eventName={event.name}
        importer={(source, dryRun) => studentsApi.importList(internshipId, event.id, source, dryRun)}
        onDone={() => void queryClient.invalidateQueries({ queryKey: ourInternshipsKeys.all })}
        onClose={onClose}
      />
    );
  }
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Import students</DialogTitle>
          <DialogDescription>Choose the event the imported students are registered for.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="imp-event">Event</Label>
            <EventSelect id="imp-event" destinations={destinations.data ?? []} value={chosen} onChange={setEventId} />
            {destinations.isSuccess && all.length === 0 && <p className="text-xs text-muted-foreground">There is no event to import into yet. Create one under Institutions.</p>}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button disabled={!chosen} onClick={() => setStarted(true)}>
              Continue
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/**
 * The internship's students: add one, import a list, fetch the people of the events' linked exams and hackathons (so their
 * marks and team scores show), and edit or remove students from the table. Everything stays inside the internship's scope.
 */
export function StudentsManager({
  internshipId,
  rows,
  showInstitution,
  pending,
  canManage,
  onSelect,
}: {
  internshipId: string;
  rows: StudentPerformance[];
  showInstitution: boolean;
  pending: boolean;
  canManage: boolean;
  onSelect: (studentIds: string[]) => void;
}) {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);
  const [editing, setEditing] = useState<StudentPerformance | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ourInternshipsKeys.all });

  const sync = useMutation({
    mutationFn: () => studentsApi.sync(internshipId),
    onSuccess: (result) => {
      setNotice(result.message);
      void refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (row: StudentPerformance) => studentsApi.remove(internshipId, row.student_id, row.event_id),
    onSuccess: () => {
      setNotice(null);
      void refresh();
    },
  });

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-2xl text-sm text-muted-foreground">
            Add students here, import a list, or fetch the people of the exams and hackathons linked to the events, so their marks and team scores show against them.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={sync.isPending} onClick={() => sync.mutate()}>
              <Download className="h-4 w-4" />
              {sync.isPending ? "Fetching..." : "Fetch from exams & hackathons"}
            </Button>
            <Button variant="outline" onClick={() => setImporting(true)}>
              <Upload className="h-4 w-4" />
              Import list
            </Button>
            <Button onClick={() => setAdding(true)}>
              <UserPlus className="h-4 w-4" />
              Add student
            </Button>
          </div>
        </div>
      )}
      {notice && <p className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200">{notice}</p>}
      {(sync.isError || remove.isError) && <p className="text-sm text-destructive">{errorMessage(sync.error ?? remove.error, "That did not work.")}</p>}

      {rows.length === 0 ? (
        <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">No students yet. Add one, import a list, or fetch the people of the linked exams and hackathons.</p>
      ) : (
        <StudentWiseView
          rows={rows}
          showInstitution={showInstitution}
          pending={pending}
          onSelect={onSelect}
          onEdit={canManage ? setEditing : undefined}
          onRemove={
            canManage
              ? (row) => {
                  if (window.confirm(`Take ${row.name} off ${row.event_name}? They stay at the institution and in their other events.`)) remove.mutate(row);
                }
              : undefined
          }
        />
      )}

      {adding && <InternshipStudentDialog internshipId={internshipId} onClose={() => setAdding(false)} />}
      {editing && <InternshipStudentDialog internshipId={internshipId} student={editing} onClose={() => setEditing(null)} />}
      {importing && <ImportFlow internshipId={internshipId} onClose={() => setImporting(false)} />}
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2, Upload, UserPlus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type InstitutionStudent, institutionsApi, institutionsKeys } from "@/features/institutions/api/institutions-api";
import { StudentFormDialog } from "@/features/institutions/components/student-form-dialog";
import { StudentImportDialog } from "@/features/institutions/components/student-import-dialog";
import { errorMessage } from "@/features/institutions/lib/format";
import { useDebounced } from "@/features/institutions/lib/use-debounced";

/** Every student at the institution, across all its events: search, filter by event, correct details, import more. */
export function InstitutionStudentsTab({ institutionId }: { institutionId: string }) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [eventId, setEventId] = useState("");
  const [importing, setImporting] = useState(false);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<InstitutionStudent | null>(null);
  const q = useDebounced(search.trim());

  const events = useQuery({ queryKey: institutionsKeys.events(institutionId), queryFn: () => institutionsApi.events(institutionId) });
  const students = useQuery({
    queryKey: institutionsKeys.students(institutionId, q, eventId),
    queryFn: () => institutionsApi.students(institutionId, q, eventId || undefined),
  });
  const remove = useMutation({
    mutationFn: (id: string) => institutionsApi.removeStudent(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: institutionsKeys.all }),
  });

  const confirmRemove = (s: InstitutionStudent) => {
    const where = s.events.length ? ` and from ${s.events.length} event${s.events.length === 1 ? "" : "s"}` : "";
    if (window.confirm(`Remove ${s.name} from this institution${where}? This cannot be undone.`)) remove.mutate(s.id);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Input
            aria-label="Search students"
            placeholder="Search name, email or phone"
            className="w-72"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            aria-label="Filter by event"
            className="rounded-md border bg-background px-3 py-2 text-sm"
            value={eventId}
            onChange={(e) => setEventId(e.target.value)}
          >
            <option value="">All events</option>
            {events.data?.map((ev) => (
              <option key={ev.id} value={ev.id}>
                {ev.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex gap-2">
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
      <p className="text-xs text-muted-foreground">
        To register students for a particular event, open that event and import the list there. Importing here only adds them
        to the institution.
      </p>

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
              {q || eventId ? "No student matches." : "No students yet. Import a list or add one by hand."}
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Events</TableHead>
                  <TableHead className="w-24" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {students.data?.items.map((s) => (
                  <TableRow key={s.id}>
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
                      <div className="flex flex-wrap gap-1">
                        {s.events.length === 0 && <span className="text-muted-foreground">—</span>}
                        {s.events.map((e) => (
                          <Link key={e.event_id} to={`/institutions/${institutionId}/events/${e.event_id}`}>
                            <Badge variant="outline" className="hover:bg-muted">
                              {e.event_name}
                            </Badge>
                          </Link>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" aria-label={`Edit ${s.name}`} onClick={() => setEditing(s)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" aria-label={`Remove ${s.name}`} onClick={() => confirmRemove(s)}>
                          <Trash2 className="h-4 w-4" />
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
      {students.data && <p className="text-xs text-muted-foreground">{students.data.total} student{students.data.total === 1 ? "" : "s"}</p>}
      {remove.isError && <p className="text-sm text-destructive">{errorMessage(remove.error, "Could not remove the student.")}</p>}

      {importing && <StudentImportDialog institutionId={institutionId} onClose={() => setImporting(false)} />}
      {adding && <StudentFormDialog institutionId={institutionId} onClose={() => setAdding(false)} />}
      {editing && (
        <StudentFormDialog
          institutionId={institutionId}
          student={{ id: editing.id, name: editing.name, email: editing.email, phone: editing.phone, details: editing.details }}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

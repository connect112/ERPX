import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Download, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { institutionsApi, institutionsKeys } from "@/features/institutions/api/institutions-api";
import { EventFormDialog } from "@/features/institutions/components/event-form-dialog";
import { InstitutionFormDialog } from "@/features/institutions/components/institution-form-dialog";
import { InstitutionStudentsTab } from "@/features/institutions/components/institution-students-tab";
import { errorMessage, eventStatusBadge, eventTypeLabels, formatBytes, formatDateRange } from "@/features/institutions/lib/format";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      {/* a long email address wraps inside its column instead of running over the next one */}
      <dd className="mt-0.5 text-sm [overflow-wrap:anywhere]">{children || <span className="text-muted-foreground">—</span>}</dd>
    </div>
  );
}

export function InstitutionDetailPage() {
  const { institutionId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("overview");
  const [editing, setEditing] = useState(false);
  const [addingEvent, setAddingEvent] = useState(false);

  const institution = useQuery({ queryKey: institutionsKeys.detail(institutionId), queryFn: () => institutionsApi.get(institutionId) });
  const events = useQuery({ queryKey: institutionsKeys.events(institutionId), queryFn: () => institutionsApi.events(institutionId) });

  const remove = useMutation({
    mutationFn: () => institutionsApi.remove(institutionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: institutionsKeys.all });
      navigate("/institutions");
    },
  });
  const download = useMutation({
    mutationFn: () => institutionsApi.downloadMou(institutionId, institution.data?.mou_filename ?? "mou"),
  });

  if (institution.isLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (institution.isError || !institution.data) {
    return (
      <div className="space-y-3 p-6">
        <p className="text-sm text-destructive">Could not load this institution.</p>
        <Button variant="outline" onClick={() => navigate("/institutions")}>
          Back to institutions
        </Button>
      </div>
    );
  }
  const i = institution.data;

  const confirmDelete = () => {
    const detail =
      i.event_count || i.student_count
        ? ` This also deletes its ${i.event_count} event${i.event_count === 1 ? "" : "s"} and ${i.student_count} student${i.student_count === 1 ? "" : "s"}. Exams and hackathons linked to its events are kept.`
        : "";
    if (window.confirm(`Delete ${i.name}?${detail} This cannot be undone.`)) remove.mutate();
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <Link to="/institutions" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Institutions
        </Link>
        <div className="mt-2 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">{i.name}</h1>
            <p className="text-sm text-muted-foreground">
              {i.location} · {i.event_count} event{i.event_count === 1 ? "" : "s"} · {i.student_count} student{i.student_count === 1 ? "" : "s"}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setEditing(true)}>
              <Pencil className="h-4 w-4" />
              Edit
            </Button>
            <Button variant="outline" onClick={confirmDelete} disabled={remove.isPending}>
              <Trash2 className="h-4 w-4" />
              Delete
            </Button>
          </div>
        </div>
        {remove.isError && <p className="mt-2 text-sm text-destructive">{errorMessage(remove.error, "Could not delete the institution.")}</p>}
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="events">Events ({i.event_count})</TabsTrigger>
          <TabsTrigger value="students">Students ({i.student_count})</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Faculty contact</CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="grid gap-3 sm:grid-cols-2">
                  <Field label="Name">{i.faculty_name}</Field>
                  <Field label="Designation">{i.faculty_designation}</Field>
                  <Field label="Email">{i.faculty_email && <a className="underline" href={`mailto:${i.faculty_email}`}>{i.faculty_email}</a>}</Field>
                  <Field label="Phone">{i.faculty_phone && <a className="underline" href={`tel:${i.faculty_phone}`}>{i.faculty_phone}</a>}</Field>
                </dl>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">MOU</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {i.mou_details && <p className="whitespace-pre-wrap text-sm">{i.mou_details}</p>}
                {i.mou_filename ? (
                  <div className="flex items-center justify-between gap-3 rounded-md border p-3 text-sm">
                    <span>
                      {i.mou_filename} <span className="text-muted-foreground">({formatBytes(i.mou_size_bytes)})</span>
                    </span>
                    <Button variant="outline" size="sm" disabled={download.isPending} onClick={() => download.mutate()}>
                      <Download className="h-4 w-4" />
                      Download
                    </Button>
                  </div>
                ) : (
                  !i.mou_details && <p className="text-sm text-muted-foreground">No MOU recorded. Edit the institution to add details or upload the document.</p>
                )}
                {download.isError && <p className="text-sm text-destructive">{errorMessage(download.error, "Could not download the document.")}</p>}
              </CardContent>
            </Card>
          </div>
          {i.notes && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Additional details</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap text-sm">{i.notes}</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="events" className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => setAddingEvent(true)}>
              <Plus className="h-4 w-4" />
              New event
            </Button>
          </div>
          <Card>
            <CardContent className="p-0">
              {events.isLoading ? (
                <div className="space-y-2 p-6">
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : (events.data?.length ?? 0) === 0 ? (
                <p className="p-8 text-center text-sm text-muted-foreground">No events yet. Create a workshop, hackathon or exam for this institution.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Event</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Dates</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Students</TableHead>
                      <TableHead>Exams</TableHead>
                      <TableHead>Hackathons</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {events.data?.map((e) => (
                      <TableRow key={e.id} className="cursor-pointer" onClick={() => navigate(`/institutions/${institutionId}/events/${e.id}`)}>
                        <TableCell className="font-medium">{e.name}</TableCell>
                        <TableCell>{eventTypeLabels[e.event_type]}</TableCell>
                        <TableCell>{formatDateRange(e.start_date, e.end_date)}</TableCell>
                        <TableCell>
                          <Badge variant={eventStatusBadge[e.status].variant}>{eventStatusBadge[e.status].label}</Badge>
                        </TableCell>
                        <TableCell>
                          {e.student_count}
                          {e.max_capacity ? <span className="text-muted-foreground"> / {e.max_capacity}</span> : null}
                        </TableCell>
                        <TableCell>{e.exam_count}</TableCell>
                        <TableCell>{e.hackathon_count}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="students">
          <InstitutionStudentsTab institutionId={institutionId} />
        </TabsContent>
      </Tabs>

      {editing && <InstitutionFormDialog institution={i} onClose={() => setEditing(false)} />}
      {addingEvent && (
        <EventFormDialog
          institutionId={institutionId}
          onClose={() => setAddingEvent(false)}
          onSaved={(e) => navigate(`/institutions/${institutionId}/events/${e.id}`)}
        />
      )}
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { institutionsApi, institutionsKeys } from "@/features/institutions/api/institutions-api";
import { EventExamsTab } from "@/features/institutions/components/event-exams-tab";
import { EventFormDialog } from "@/features/institutions/components/event-form-dialog";
import { EventHackathonsTab } from "@/features/institutions/components/event-hackathons-tab";
import { EventStudentsTab } from "@/features/institutions/components/event-students-tab";
import { errorMessage, eventStatusBadge, eventTypeLabels, formatDateRange } from "@/features/institutions/lib/format";

export function EventDetailPage() {
  const { institutionId = "", eventId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("students");
  const [editing, setEditing] = useState(false);

  const event = useQuery({ queryKey: institutionsKeys.event(eventId), queryFn: () => institutionsApi.event(eventId) });
  const remove = useMutation({
    mutationFn: () => institutionsApi.removeEvent(eventId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: institutionsKeys.all });
      navigate(`/institutions/${institutionId}`);
    },
  });

  if (event.isLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (event.isError || !event.data) {
    return (
      <div className="space-y-3 p-6">
        <p className="text-sm text-destructive">Could not load this event.</p>
        <Button variant="outline" onClick={() => navigate(`/institutions/${institutionId}`)}>
          Back to the institution
        </Button>
      </div>
    );
  }
  const e = event.data;
  const status = eventStatusBadge[e.status];

  const confirmDelete = () => {
    const linked = e.exam_count + e.hackathon_count;
    const detail = ` This removes its ${e.student_count} registration${e.student_count === 1 ? "" : "s"}.${linked ? " Its exams and hackathons are kept, just no longer linked to it." : ""}`;
    if (window.confirm(`Delete ${e.name}?${detail} This cannot be undone.`)) remove.mutate();
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <Link to={`/institutions/${e.institution_id}`} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          {e.institution_name}
        </Link>
        <div className="mt-2 flex items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold">{e.name}</h1>
              <Badge variant={status.variant}>{status.label}</Badge>
              <Badge variant="outline">{eventTypeLabels[e.event_type]}</Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              {formatDateRange(e.start_date, e.end_date)} · {e.student_count}
              {e.max_capacity ? ` of ${e.max_capacity}` : ""} student{e.student_count === 1 ? "" : "s"}
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
        {remove.isError && <p className="mt-2 text-sm text-destructive">{errorMessage(remove.error, "Could not delete the event.")}</p>}
      </div>

      {e.description && (
        <Card>
          <CardContent className="p-4">
            <p className="whitespace-pre-wrap text-sm">{e.description}</p>
          </CardContent>
        </Card>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="students">Students ({e.student_count})</TabsTrigger>
          <TabsTrigger value="exams">Exams ({e.exam_count})</TabsTrigger>
          <TabsTrigger value="hackathons">Hackathons ({e.hackathon_count})</TabsTrigger>
        </TabsList>
        <TabsContent value="students">
          <EventStudentsTab event={e} />
        </TabsContent>
        <TabsContent value="exams">
          <EventExamsTab event={e} />
        </TabsContent>
        <TabsContent value="hackathons">
          <EventHackathonsTab event={e} />
        </TabsContent>
      </Tabs>

      {editing && <EventFormDialog institutionId={e.institution_id} event={e} onClose={() => setEditing(false)} />}
    </div>
  );
}

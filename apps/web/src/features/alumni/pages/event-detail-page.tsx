import { ArrowLeft, Pencil } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useChangeEventStatus, useEvent, useEventRegistrations } from "@/features/alumni/api/alumni-hooks";
import { EventFormDialog } from "@/features/alumni/components/event-form-dialog";
import { EventStatusBadge } from "@/features/alumni/components/event-status-badge";
import { RegistrationRow } from "@/features/alumni/components/registration-row";
import {
  type EventStatus,
  eventStatusLabels,
  eventStatusValues,
} from "@/features/alumni/schemas/event-schemas";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function EventDetailPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const navigate = useNavigate();
  const { data: event, isLoading } = useEvent(eventId);
  const { data: registrations, isLoading: registrationsLoading } = useEventRegistrations(eventId);
  const changeStatus = useChangeEventStatus(eventId ?? "");
  const [editOpen, setEditOpen] = useState(false);

  if (isLoading || !event) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/alumni/events")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{event.title}</h1>
            <div className="mt-1 flex items-center gap-2">
              <EventStatusBadge status={event.status} />
            </div>
          </div>
        </div>
        <Button variant="outline" onClick={() => setEditOpen(true)}>
          <Pencil className="h-4 w-4" />
          Edit
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Event details</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Mode" value={<span className="capitalize">{event.mode}</span>} />
              <DetailRow label="Event date" value={new Date(event.event_date).toLocaleDateString()} />
              <DetailRow
                label="Registration deadline"
                value={
                  event.registration_deadline
                    ? new Date(event.registration_deadline).toLocaleDateString()
                    : "—"
                }
              />
              <DetailRow label="Venue" value={event.venue || "—"} />
              <DetailRow label="Meeting link" value={event.meeting_link || "—"} />
              {event.description && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Description</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{event.description}</p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Registrations</CardTitle>
              <CardDescription>{registrations?.length ?? 0} alumni registered.</CardDescription>
            </CardHeader>
            <CardContent>
              {registrationsLoading ? (
                <Skeleton className="h-24 w-full" />
              ) : registrations && registrations.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Alumni</TableHead>
                      <TableHead>Registered</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {registrations.map((registration) => (
                      <RegistrationRow key={registration.id} eventId={event.id} registration={registration} />
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="py-4 text-center text-sm text-muted-foreground">No registrations yet.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Change status</CardTitle>
            </CardHeader>
            <CardContent>
              <Select
                value={event.status}
                onValueChange={(value) => changeStatus.mutate(value as EventStatus)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {eventStatusValues.map((s) => (
                    <SelectItem key={s} value={s}>
                      {eventStatusLabels[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
        </div>
      </div>

      <EventFormDialog open={editOpen} onOpenChange={setEditOpen} event={event} />
    </div>
  );
}

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDeleteEvent, useEventsList } from "@/features/events/api/events-hooks";
import { EventFormDialog } from "@/features/events/components/event-form-dialog";
import { EventTypeBadge } from "@/features/events/components/event-type-badge";
import {
  type EventType,
  eventTypeLabels,
  eventTypeValues,
} from "@/features/events/schemas/event-schemas";

export function EventsListPage() {
  const [eventType, setEventType] = useState<EventType | "all">("all");
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useEventsList({
    event_type: eventType === "all" ? undefined : eventType,
    limit: 100,
  });
  const deleteEvent = useDeleteEvent();

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Organization Calendar</h1>
          <p className="mt-1 text-muted-foreground">
            Holidays, meetings, and announcements for everyone in the organization.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Event
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select value={eventType} onValueChange={(value) => setEventType(value as EventType | "all")}>
            <SelectTrigger className="sm:w-56">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              {eventTypeValues.map((t) => (
                <SelectItem key={t} value={t}>
                  {eventTypeLabels[t]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load events. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No events scheduled. Create the first one to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>When</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="font-medium">{event.title}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {event.is_all_day
                        ? new Date(event.start_at).toLocaleDateString()
                        : new Date(event.start_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{event.location || "—"}</TableCell>
                    <TableCell>
                      <EventTypeBadge type={event.event_type} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => deleteEvent.mutate(event.id)}
                        aria-label={`Delete ${event.title}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <EventFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}

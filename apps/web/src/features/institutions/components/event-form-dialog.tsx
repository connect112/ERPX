import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type EventPayload,
  type EventStatus,
  type EventType,
  type InstitutionEvent,
  institutionsApi,
  institutionsKeys,
} from "@/features/institutions/api/institutions-api";
import { errorMessage, eventStatusBadge, eventTypeLabels } from "@/features/institutions/lib/format";

const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";

/** Create an event at an institution, or edit one. */
export function EventFormDialog({
  institutionId,
  event,
  onClose,
  onSaved,
}: {
  institutionId: string;
  event?: InstitutionEvent;
  onClose: () => void;
  onSaved?: (event: InstitutionEvent) => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(event?.name ?? "");
  const [type, setType] = useState<EventType>(event?.event_type ?? "workshop");
  const [start, setStart] = useState(event?.start_date ?? "");
  const [end, setEnd] = useState(event?.end_date ?? "");
  const [description, setDescription] = useState(event?.description ?? "");
  const [capacity, setCapacity] = useState(event?.max_capacity ? String(event.max_capacity) : "");
  const [status, setStatus] = useState<EventStatus>(event?.status ?? "upcoming");

  const save = useMutation({
    mutationFn: () => {
      const payload: EventPayload = {
        name: name.trim(),
        event_type: type,
        start_date: start,
        end_date: end || start,
        description: description.trim() || null,
        max_capacity: capacity.trim() ? Number(capacity) : null,
        status,
      };
      return event ? institutionsApi.updateEvent(event.id, payload) : institutionsApi.createEvent(institutionId, payload);
    },
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: institutionsKeys.all });
      onSaved?.(saved);
      onClose();
    },
  });

  const capacityOk = !capacity.trim() || (Number.isInteger(Number(capacity)) && Number(capacity) >= 1);
  const datesOk = !!start && (!end || end >= start);
  const valid = name.trim().length >= 2 && datesOk && capacityOk;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{event ? "Edit event" : "New event"}</DialogTitle>
          <DialogDescription>A workshop, hackathon, exam or anything else held at this institution.</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid && !save.isPending) save.mutate();
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="event-name">Event name</Label>
            <Input id="event-name" value={name} maxLength={255} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="event-type">Type</Label>
              <select id="event-type" className={selectClass} value={type} onChange={(e) => setType(e.target.value as EventType)}>
                {Object.entries(eventTypeLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="event-status">Status</Label>
              <select id="event-status" className={selectClass} value={status} onChange={(e) => setStatus(e.target.value as EventStatus)}>
                {Object.entries(eventStatusBadge).map(([value, { label }]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="event-start">Start date</Label>
              <Input id="event-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="event-end">End date</Label>
              <Input id="event-end" type="date" min={start || undefined} value={end} onChange={(e) => setEnd(e.target.value)} />
              {!datesOk && end && <p className="text-xs text-destructive">The end date cannot be before the start date.</p>}
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="event-capacity">
              Maximum capacity <span className="text-xs text-muted-foreground">(optional, leave empty for no limit)</span>
            </Label>
            <Input id="event-capacity" inputMode="numeric" value={capacity} onChange={(e) => setCapacity(e.target.value.replace(/\D/g, ""))} />
            {!capacityOk && <p className="text-xs text-destructive">Enter a whole number, 1 or more.</p>}
          </div>
          <div className="space-y-1">
            <Label htmlFor="event-description">Description</Label>
            <Textarea id="event-description" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save the event.")}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!valid || save.isPending}>
              {save.isPending ? "Saving..." : event ? "Save changes" : "Create event"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

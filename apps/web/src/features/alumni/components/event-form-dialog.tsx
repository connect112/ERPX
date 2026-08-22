import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { AlumniEventPublic } from "@/features/alumni/api/alumni-api";
import { useCreateEvent, useUpdateEvent } from "@/features/alumni/api/alumni-hooks";
import {
  type EventFormValues,
  eventFormSchema,
  eventModeLabels,
  eventModeValues,
} from "@/features/alumni/schemas/event-schemas";

interface EventFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  event?: AlumniEventPublic;
}

const emptyValues: EventFormValues = {
  title: "",
  description: "",
  mode: "virtual",
  venue: "",
  meetingLink: "",
  eventDate: "",
  registrationDeadline: "",
};

export function EventFormDialog({ open, onOpenChange, event }: EventFormDialogProps) {
  const isEditing = !!event;
  const createEvent = useCreateEvent();
  const updateEvent = useUpdateEvent(event?.id ?? "");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EventFormValues>({
    resolver: zodResolver(eventFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        event
          ? {
              title: event.title,
              description: event.description ?? "",
              mode: event.mode,
              venue: event.venue ?? "",
              meetingLink: event.meeting_link ?? "",
              eventDate: event.event_date,
              registrationDeadline: event.registration_deadline ?? "",
            }
          : emptyValues
      );
    }
  }, [open, event, reset]);

  const mutation = isEditing ? updateEvent : createEvent;

  const onSubmit = (values: EventFormValues) => {
    const payload = {
      title: values.title,
      description: values.description || undefined,
      mode: values.mode,
      venue: values.venue || undefined,
      meeting_link: values.meetingLink || undefined,
      event_date: values.eventDate,
      registration_deadline: values.registrationDeadline || undefined,
    };
    mutation.mutate(payload, { onSuccess: () => onOpenChange(false) });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit alumni event" : "New alumni event"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title" required>Title</Label>
            <Input id="title" {...register("title")} />
            {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="mode" required>Mode</Label>
              <Controller
                control={control}
                name="mode"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="mode">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {eventModeValues.map((m) => (
                        <SelectItem key={m} value={m}>
                          {eventModeLabels[m]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="eventDate" required>Event date</Label>
              <Input id="eventDate" type="date" {...register("eventDate")} />
              {errors.eventDate && (
                <p className="text-sm text-destructive">{errors.eventDate.message}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="venue">Venue</Label>
              <Input id="venue" {...register("venue")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="meetingLink">Meeting link</Label>
              <Input id="meetingLink" {...register("meetingLink")} />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="registrationDeadline">Registration deadline</Label>
            <Input id="registrationDeadline" type="date" {...register("registrationDeadline")} />
          </div>

          {mutation.isError && (
            <p className="text-sm text-destructive">
              {(mutation.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create event"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

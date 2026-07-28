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
import { useCreateEvent } from "@/features/events/api/events-hooks";
import {
  type EventFormValues,
  eventFormSchema,
  eventTypeLabels,
  eventTypeValues,
} from "@/features/events/schemas/event-schemas";

interface EventFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const emptyValues: EventFormValues = {
  title: "",
  description: "",
  eventType: "other",
  startAt: "",
  endAt: "",
  location: "",
  isAllDay: false,
};

export function EventFormDialog({ open, onOpenChange }: EventFormDialogProps) {
  const createEvent = useCreateEvent();

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
    if (open) reset(emptyValues);
  }, [open, reset]);

  const onSubmit = (values: EventFormValues) => {
    createEvent.mutate(
      {
        title: values.title,
        description: values.description || undefined,
        event_type: values.eventType,
        start_at: new Date(values.startAt).toISOString(),
        end_at: values.endAt ? new Date(values.endAt).toISOString() : undefined,
        location: values.location || undefined,
        is_all_day: values.isAllDay,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>New event</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input id="title" {...register("title")} />
            {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="eventType">Type</Label>
              <Controller
                control={control}
                name="eventType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="eventType">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {eventTypeValues.map((t) => (
                        <SelectItem key={t} value={t}>
                          {eventTypeLabels[t]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="location">Location</Label>
              <Input id="location" {...register("location")} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="startAt">Starts</Label>
              <Input id="startAt" type="datetime-local" {...register("startAt")} />
              {errors.startAt && <p className="text-sm text-destructive">{errors.startAt.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="endAt">Ends (optional)</Label>
              <Input id="endAt" type="datetime-local" {...register("endAt")} />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input
              id="isAllDay"
              type="checkbox"
              className="h-4 w-4 rounded border-input"
              {...register("isAllDay")}
            />
            <Label htmlFor="isAllDay" className="cursor-pointer font-normal">
              All-day event
            </Label>
          </div>

          {createEvent.isError && (
            <p className="text-sm text-destructive">
              {(createEvent.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Could not create event."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createEvent.isPending}>
              {createEvent.isPending ? "Creating..." : "Create event"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

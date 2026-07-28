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
import type { WorkshopPublic } from "@/features/workshops/api/workshops-api";
import { useCreateWorkshop, useUpdateWorkshop } from "@/features/workshops/api/workshops-hooks";
import {
  type WorkshopFormValues,
  workshopFormSchema,
  workshopModeLabels,
  workshopModeValues,
} from "@/features/workshops/schemas/workshop-schemas";

interface WorkshopFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workshop?: WorkshopPublic;
}

const emptyValues: WorkshopFormValues = {
  code: "",
  title: "",
  description: "",
  mode: "physical",
  venue: "",
  meetingLink: "",
  workshopDate: "",
  startTime: "",
  endTime: "",
  capacity: undefined,
  fee: undefined,
};

export function WorkshopFormDialog({ open, onOpenChange, workshop }: WorkshopFormDialogProps) {
  const isEditing = !!workshop;
  const createWorkshop = useCreateWorkshop();
  const updateWorkshop = useUpdateWorkshop(workshop?.id ?? "");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<WorkshopFormValues>({
    resolver: zodResolver(workshopFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        workshop
          ? {
              code: workshop.code,
              title: workshop.title,
              description: workshop.description ?? "",
              mode: workshop.mode,
              venue: workshop.venue ?? "",
              meetingLink: workshop.meeting_link ?? "",
              workshopDate: workshop.workshop_date,
              startTime: workshop.start_time,
              endTime: workshop.end_time,
              capacity: workshop.capacity ?? undefined,
              fee: workshop.fee,
            }
          : emptyValues
      );
    }
  }, [open, workshop, reset]);

  const mutation = isEditing ? updateWorkshop : createWorkshop;

  const onSubmit = (values: WorkshopFormValues) => {
    const shared = {
      title: values.title,
      description: values.description || undefined,
      mode: values.mode,
      venue: values.venue || undefined,
      meeting_link: values.meetingLink || undefined,
      workshop_date: values.workshopDate,
      start_time: values.startTime,
      end_time: values.endTime,
      capacity: values.capacity,
      fee: values.fee,
    };
    if (isEditing) {
      updateWorkshop.mutate(shared, { onSuccess: () => onOpenChange(false) });
    } else {
      createWorkshop.mutate({ code: values.code, ...shared }, { onSuccess: () => onOpenChange(false) });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit workshop" : "New workshop"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="code">Code</Label>
              <Input id="code" disabled={isEditing} {...register("code")} />
              {errors.code && <p className="text-sm text-destructive">{errors.code.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="mode">Mode</Label>
              <Controller
                control={control}
                name="mode"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="mode">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {workshopModeValues.map((m) => (
                        <SelectItem key={m} value={m}>
                          {workshopModeLabels[m]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="capacity">Capacity</Label>
              <Input id="capacity" type="number" min={1} {...register("capacity")} />
              {errors.capacity && (
                <p className="text-sm text-destructive">{errors.capacity.message}</p>
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

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="workshopDate">Date</Label>
              <Input id="workshopDate" type="date" {...register("workshopDate")} />
              {errors.workshopDate && (
                <p className="text-sm text-destructive">{errors.workshopDate.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="startTime">Start time</Label>
              <Input id="startTime" type="time" {...register("startTime")} />
              {errors.startTime && (
                <p className="text-sm text-destructive">{errors.startTime.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="endTime">End time</Label>
              <Input id="endTime" type="time" {...register("endTime")} />
              {errors.endTime && <p className="text-sm text-destructive">{errors.endTime.message}</p>}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="fee">Fee</Label>
            <Input id="fee" type="number" step="0.01" min={0} {...register("fee")} />
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create workshop"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

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
import { Textarea } from "@/components/ui/textarea";
import type { HackathonPublic } from "@/features/hackathons/api/hackathons-api";
import { useCreateHackathon, useUpdateHackathon } from "@/features/hackathons/api/hackathons-hooks";
import {
  type HackathonFormValues,
  hackathonFormSchema,
} from "@/features/hackathons/schemas/hackathon-schemas";

interface HackathonFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  hackathon?: HackathonPublic;
}

const emptyValues: HackathonFormValues = {
  code: "",
  title: "",
  theme: "",
  description: "",
  registrationDeadline: "",
  startDate: "",
  endDate: "",
  maxTeamSize: undefined,
  prizePool: undefined,
};

export function HackathonFormDialog({ open, onOpenChange, hackathon }: HackathonFormDialogProps) {
  const isEditing = !!hackathon;
  const createHackathon = useCreateHackathon();
  const updateHackathon = useUpdateHackathon(hackathon?.id ?? "");

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<HackathonFormValues>({
    resolver: zodResolver(hackathonFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        hackathon
          ? {
              code: hackathon.code,
              title: hackathon.title,
              theme: hackathon.theme ?? "",
              description: hackathon.description ?? "",
              registrationDeadline: hackathon.registration_deadline,
              startDate: hackathon.start_date,
              endDate: hackathon.end_date,
              maxTeamSize: hackathon.max_team_size,
              prizePool: hackathon.prize_pool ?? undefined,
            }
          : emptyValues
      );
    }
  }, [open, hackathon, reset]);

  const mutation = isEditing ? updateHackathon : createHackathon;

  const onSubmit = (values: HackathonFormValues) => {
    const shared = {
      title: values.title,
      theme: values.theme || undefined,
      description: values.description || undefined,
      registration_deadline: values.registrationDeadline,
      start_date: values.startDate,
      end_date: values.endDate,
      max_team_size: values.maxTeamSize,
      prize_pool: values.prizePool,
    };
    if (isEditing) {
      updateHackathon.mutate(shared, { onSuccess: () => onOpenChange(false) });
    } else {
      createHackathon.mutate({ code: values.code, ...shared }, { onSuccess: () => onOpenChange(false) });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit hackathon" : "New hackathon"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="code" required>Code</Label>
              <Input id="code" disabled={isEditing} {...register("code")} />
              {errors.code && <p className="text-sm text-destructive">{errors.code.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="title" required>Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="theme">Theme</Label>
            <Input id="theme" {...register("theme")} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="registrationDeadline" required>Registration deadline</Label>
              <Input id="registrationDeadline" type="date" {...register("registrationDeadline")} />
              {errors.registrationDeadline && (
                <p className="text-sm text-destructive">{errors.registrationDeadline.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="startDate" required>Start date</Label>
              <Input id="startDate" type="date" {...register("startDate")} />
              {errors.startDate && (
                <p className="text-sm text-destructive">{errors.startDate.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="endDate" required>End date</Label>
              <Input id="endDate" type="date" {...register("endDate")} />
              {errors.endDate && <p className="text-sm text-destructive">{errors.endDate.message}</p>}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="maxTeamSize">Max team size</Label>
              <Input id="maxTeamSize" type="number" min={1} max={20} {...register("maxTeamSize")} />
              {errors.maxTeamSize && (
                <p className="text-sm text-destructive">{errors.maxTeamSize.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="prizePool">Prize pool</Label>
              <Input id="prizePool" type="number" step="0.01" min={0} {...register("prizePool")} />
              {errors.prizePool && (
                <p className="text-sm text-destructive">{errors.prizePool.message}</p>
              )}
            </div>
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create hackathon"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

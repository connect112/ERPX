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
import type { InternshipPostingPublic } from "@/features/internships/api/internships-api";
import {
  useCompaniesList,
  useCreatePosting,
  useUpdatePosting,
} from "@/features/internships/api/internships-hooks";
import { type PostingFormValues, postingFormSchema } from "@/features/internships/schemas/posting-schemas";

interface PostingFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  posting?: InternshipPostingPublic;
}

const emptyValues: PostingFormValues = {
  companyId: "",
  title: "",
  description: "",
  durationMonths: undefined,
  stipend: undefined,
  location: "",
  requiredSkills: "",
  applicationDeadline: "",
};

export function PostingFormDialog({ open, onOpenChange, posting }: PostingFormDialogProps) {
  const isEditing = !!posting;
  const { data: companies } = useCompaniesList({ limit: 200 });
  const createPosting = useCreatePosting();
  const updatePosting = useUpdatePosting(posting?.id ?? "");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PostingFormValues>({
    resolver: zodResolver(postingFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        posting
          ? {
              companyId: posting.company_id,
              title: posting.title,
              description: posting.description ?? "",
              durationMonths: posting.duration_months ?? undefined,
              stipend: posting.stipend ?? undefined,
              location: posting.location ?? "",
              requiredSkills: posting.required_skills ?? "",
              applicationDeadline: posting.application_deadline ?? "",
            }
          : emptyValues
      );
    }
  }, [open, posting, reset]);

  const mutation = isEditing ? updatePosting : createPosting;

  const onSubmit = (values: PostingFormValues) => {
    const shared = {
      title: values.title,
      description: values.description || undefined,
      duration_months: values.durationMonths,
      stipend: values.stipend,
      location: values.location || undefined,
      required_skills: values.requiredSkills || undefined,
      application_deadline: values.applicationDeadline || undefined,
    };
    if (isEditing) {
      updatePosting.mutate(shared, { onSuccess: () => onOpenChange(false) });
    } else {
      createPosting.mutate(
        { company_id: values.companyId, ...shared },
        { onSuccess: () => onOpenChange(false) }
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit internship posting" : "New internship posting"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="companyId">Company</Label>
            <Controller
              control={control}
              name="companyId"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange} disabled={isEditing}>
                  <SelectTrigger id="companyId">
                    <SelectValue placeholder="Select a company" />
                  </SelectTrigger>
                  <SelectContent>
                    {companies?.items.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.companyId && (
              <p className="text-sm text-destructive">{errors.companyId.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input id="title" {...register("title")} />
            {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="durationMonths">Duration (months)</Label>
              <Input
                id="durationMonths"
                type="number"
                min={1}
                max={36}
                {...register("durationMonths")}
              />
              {errors.durationMonths && (
                <p className="text-sm text-destructive">{errors.durationMonths.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="stipend">Stipend</Label>
              <Input id="stipend" type="number" step="0.01" min={0} {...register("stipend")} />
              {errors.stipend && <p className="text-sm text-destructive">{errors.stipend.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="location">Location</Label>
              <Input id="location" {...register("location")} />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="applicationDeadline">Application deadline</Label>
            <Input id="applicationDeadline" type="date" {...register("applicationDeadline")} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="requiredSkills">Required skills</Label>
            <Textarea id="requiredSkills" rows={2} {...register("requiredSkills")} />
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create posting"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

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
import { useCompaniesList } from "@/features/placements/api/placements-hooks";
import type { JobPostingPublic } from "@/features/placements/api/placements-api";
import { useCreatePosting, useUpdatePosting } from "@/features/placements/api/placements-hooks";
import {
  type PostingFormValues,
  jobTypeLabels,
  jobTypeValues,
  postingFormSchema,
} from "@/features/placements/schemas/posting-schemas";

interface PostingFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  posting?: JobPostingPublic;
}

const emptyValues: PostingFormValues = {
  companyId: "",
  title: "",
  description: "",
  jobType: "full_time",
  location: "",
  salaryMin: undefined,
  salaryMax: undefined,
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
              jobType: posting.job_type,
              location: posting.location ?? "",
              salaryMin: posting.salary_min ?? undefined,
              salaryMax: posting.salary_max ?? undefined,
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
      job_type: values.jobType,
      location: values.location || undefined,
      salary_min: values.salaryMin,
      salary_max: values.salaryMax,
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
          <DialogTitle>{isEditing ? "Edit job posting" : "New job posting"}</DialogTitle>
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

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="jobType">Job type</Label>
              <Controller
                control={control}
                name="jobType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="jobType">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {jobTypeValues.map((t) => (
                        <SelectItem key={t} value={t}>
                          {jobTypeLabels[t]}
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

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="salaryMin">Salary min</Label>
              <Input id="salaryMin" type="number" step="0.01" min={0} {...register("salaryMin")} />
              {errors.salaryMin && (
                <p className="text-sm text-destructive">{errors.salaryMin.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="salaryMax">Salary max</Label>
              <Input id="salaryMax" type="number" step="0.01" min={0} {...register("salaryMax")} />
              {errors.salaryMax && (
                <p className="text-sm text-destructive">{errors.salaryMax.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="applicationDeadline">Application deadline</Label>
              <Input id="applicationDeadline" type="date" {...register("applicationDeadline")} />
            </div>
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

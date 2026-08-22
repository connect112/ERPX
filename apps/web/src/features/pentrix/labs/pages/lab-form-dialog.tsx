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
import type { LabPublic } from "@/features/pentrix/labs/api/labs-api";
import { useCreateLab, useUpdateLab } from "@/features/pentrix/labs/api/labs-hooks";
import {
  type LabFormValues,
  labDifficultyLabels,
  labDifficultyValues,
  labFormSchema,
} from "@/features/pentrix/labs/schemas/lab-schemas";

interface LabFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lab?: LabPublic;
}

const emptyValues: LabFormValues = {
  title: "",
  slug: "",
  description: "",
  category: "",
  difficulty: "easy",
  environmentImage: "",
  points: "100",
  defaultDurationMinutes: "60",
};

export function LabFormDialog({ open, onOpenChange, lab }: LabFormDialogProps) {
  const isEditing = !!lab;
  const createLab = useCreateLab();
  const updateLab = useUpdateLab(lab?.id ?? "");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<LabFormValues>({ resolver: zodResolver(labFormSchema), defaultValues: emptyValues });

  useEffect(() => {
    if (open) {
      reset(
        lab
          ? {
              title: lab.title,
              slug: lab.slug,
              description: lab.description ?? "",
              category: lab.category,
              difficulty: lab.difficulty,
              environmentImage: lab.environment_image,
              points: String(lab.points),
              defaultDurationMinutes: String(lab.default_duration_minutes),
            }
          : emptyValues
      );
    }
  }, [open, lab, reset]);

  const onSubmit = (values: LabFormValues) => {
    const shared = {
      description: values.description || undefined,
      category: values.category,
      difficulty: values.difficulty,
      environment_image: values.environmentImage,
      points: Number(values.points),
      default_duration_minutes: Number(values.defaultDurationMinutes),
    };

    if (isEditing) {
      updateLab.mutate({ ...shared, title: values.title }, { onSuccess: () => onOpenChange(false) });
    } else {
      createLab.mutate(
        { ...shared, title: values.title, slug: values.slug },
        { onSuccess: () => onOpenChange(false) }
      );
    }
  };

  const mutation = isEditing ? updateLab : createLab;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit lab" : "New lab"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title" required>Title</Label>
            <Input id="title" {...register("title")} />
            {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
          </div>
          {!isEditing && (
            <div className="space-y-2">
              <Label htmlFor="slug" required>Slug</Label>
              <Input id="slug" placeholder="e.g. sql-injection-101" {...register("slug")} />
              {errors.slug && <p className="text-sm text-destructive">{errors.slug.message}</p>}
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="category" required>Category</Label>
              <Input id="category" placeholder="e.g. Web Exploitation" {...register("category")} />
              {errors.category && (
                <p className="text-sm text-destructive">{errors.category.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="difficulty" required>Difficulty</Label>
              <Controller
                control={control}
                name="difficulty"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="difficulty">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {labDifficultyValues.map((d) => (
                        <SelectItem key={d} value={d}>
                          {labDifficultyLabels[d]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={3} {...register("description")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="environmentImage" required>Environment image</Label>
            <Input
              id="environmentImage"
              placeholder="e.g. pentrix/web-sqli:latest"
              {...register("environmentImage")}
            />
            {errors.environmentImage && (
              <p className="text-sm text-destructive">{errors.environmentImage.message}</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="points" required>Points</Label>
              <Input id="points" type="number" {...register("points")} />
              {errors.points && <p className="text-sm text-destructive">{errors.points.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="defaultDurationMinutes" required>Duration (min)</Label>
              <Input id="defaultDurationMinutes" type="number" {...register("defaultDurationMinutes")} />
              {errors.defaultDurationMinutes && (
                <p className="text-sm text-destructive">{errors.defaultDurationMinutes.message}</p>
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create lab"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

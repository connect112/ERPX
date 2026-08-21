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
import { useCategories } from "@/features/courses/categories/api/categories-hooks";
import type { CoursePublic } from "@/features/courses/api/courses-api";
import { useCreateCourse, useUpdateCourse } from "@/features/courses/api/courses-hooks";
import {
  type CourseFormValues,
  courseFormSchema,
  courseLevelLabels,
  courseLevelValues,
} from "@/features/courses/schemas/course-schemas";

interface CourseFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  course?: CoursePublic;
}

const emptyValues: CourseFormValues = {
  categoryId: "",
  title: "",
  slug: "",
  shortDescription: "",
  description: "",
  thumbnailUrl: "",
  level: "beginner",
  durationHours: "",
  price: "",
};

export function CourseFormDialog({ open, onOpenChange, course }: CourseFormDialogProps) {
  const isEditing = !!course;
  const { data: categories } = useCategories();
  const createCourse = useCreateCourse();
  const updateCourse = useUpdateCourse(course?.id ?? "");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CourseFormValues>({ resolver: zodResolver(courseFormSchema), defaultValues: emptyValues });

  useEffect(() => {
    if (open) {
      reset(
        course
          ? {
              categoryId: course.category_id ?? "",
              title: course.title,
              slug: course.slug,
              shortDescription: course.short_description ?? "",
              description: course.description ?? "",
              thumbnailUrl: course.thumbnail_url ?? "",
              level: course.level,
              durationHours: course.duration_hours ? String(course.duration_hours) : "",
              price: String(course.price),
            }
          : emptyValues
      );
    }
  }, [open, course, reset]);

  const onSubmit = (values: CourseFormValues) => {
    const shared = {
      category_id: values.categoryId || undefined,
      short_description: values.shortDescription || undefined,
      description: values.description || undefined,
      thumbnail_url: values.thumbnailUrl || undefined,
      level: values.level,
      duration_hours: values.durationHours ? Number(values.durationHours) : undefined,
      price: values.price ? Number(values.price) : undefined,
    };

    if (isEditing) {
      updateCourse.mutate(
        { ...shared, title: values.title },
        { onSuccess: () => onOpenChange(false) }
      );
    } else {
      createCourse.mutate(
        { ...shared, title: values.title, slug: values.slug },
        { onSuccess: () => onOpenChange(false) }
      );
    }
  };

  const mutation = isEditing ? updateCourse : createCourse;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit course" : "New course"}</DialogTitle>
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
              <Input id="slug" placeholder="e.g. intro-to-python" {...register("slug")} />
              {errors.slug && <p className="text-sm text-destructive">{errors.slug.message}</p>}
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="categoryId">Category</Label>
              <Controller
                control={control}
                name="categoryId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="categoryId">
                      <SelectValue placeholder="No category" />
                    </SelectTrigger>
                    <SelectContent>
                      {categories?.map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="level" required>Level</Label>
              <Controller
                control={control}
                name="level"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="level">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {courseLevelValues.map((l) => (
                        <SelectItem key={l} value={l}>
                          {courseLevelLabels[l]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="shortDescription">Short description</Label>
            <Input id="shortDescription" {...register("shortDescription")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={3} {...register("description")} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="durationHours">Duration (hours)</Label>
              <Input id="durationHours" type="number" {...register("durationHours")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="price">Price</Label>
              <Input id="price" type="number" step="0.01" {...register("price")} />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="thumbnailUrl">Thumbnail URL</Label>
            <Input id="thumbnailUrl" {...register("thumbnailUrl")} />
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create course"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { useNavigate } from "react-router-dom";

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
import { InternshipPicker } from "@/features/courses/components/internship-picker";
import { useLinkableInternships } from "@/features/courses/lib/linkable-internships";
import { type CourseDialogValues, courseDialogSchema } from "@/features/courses/lib/dialog-schema";
import {
  type CourseTypeValue,
  courseLevelLabels,
  courseLevelValues,
  courseTypeLabels,
  courseTypeValues,
} from "@/features/courses/schemas/course-schemas";
import { errorMessage } from "@/features/institutions/lib/format";
import { onboardingApi, ourInternshipsKeys } from "@/features/our-internships/api/our-internships-api";

/** Where a New Course was started from: Our Internships → Onboarding Settings → LMS course sets all three. */
export interface CourseDialogDefaults {
  courseType?: CourseTypeValue;
  internshipId?: string;
  /** go back here (the internship's settings) once the course is created and linked */
  returnTo?: string;
}

interface CourseFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  course?: CoursePublic;
  defaults?: CourseDialogDefaults;
}

const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";

const emptyValues: CourseDialogValues = {
  courseType: "regular",
  showInternshipFee: false,
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

export function CourseFormDialog({ open, onOpenChange, course, defaults }: CourseFormDialogProps) {
  const isEditing = !!course;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: categories } = useCategories();
  const { internships } = useLinkableInternships();
  const createCourse = useCreateCourse();
  const updateCourse = useUpdateCourse(course?.id ?? "");
  const [internshipId, setInternshipId] = useState("");
  const [replace, setReplace] = useState(false);
  const [linking, setLinking] = useState(false);
  // the course exists but linking it failed: say so plainly instead of implying success
  const [partial, setPartial] = useState<{ courseId: string; message: string } | null>(null);

  const {
    register,
    control,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<CourseDialogValues>({ resolver: zodResolver(courseDialogSchema), defaultValues: emptyValues });
  const courseType = useWatch({ control, name: "courseType" });
  const showFee = useWatch({ control, name: "showInternshipFee" });

  useEffect(() => {
    if (open) {
      setPartial(null);
      setReplace(false);
      setInternshipId(!course ? defaults?.internshipId ?? "" : "");
      reset(
        course
          ? {
              courseType: course.course_type,
              showInternshipFee: course.show_internship_fee,
              categoryId: course.category_id ?? "",
              title: course.title,
              slug: course.slug,
              shortDescription: course.short_description ?? "",
              description: course.description ?? "",
              thumbnailUrl: course.thumbnail_url ?? "",
              level: course.level,
              durationHours: course.duration_hours ? String(course.duration_hours) : "",
              price: course.course_type === "internship" ? "" : String(course.price),
            }
          : { ...emptyValues, courseType: defaults?.courseType ?? "regular" }
      );
    }
  }, [open, course, defaults, reset]);

  const isInternship = courseType === "internship";
  const selected = internships.find((i) => i.id === internshipId);
  const replacing = !!selected?.lms_course_id;
  const linkedCount = course?.linked_internships.length ?? 0;
  const mutation = isEditing ? updateCourse : createCourse;

  const finish = (courseId?: string) => {
    onOpenChange(false);
    if (defaults?.returnTo) navigate(defaults.returnTo);
    else if (courseId && internshipId) navigate(`/courses/${courseId}`);
  };

  const onSubmit = (values: CourseDialogValues) => {
    const internship = values.courseType === "internship";
    const shared = {
      category_id: values.categoryId || undefined,
      short_description: values.shortDescription || undefined,
      description: values.description || undefined,
      thumbnail_url: values.thumbnailUrl || undefined,
      level: values.level,
      duration_hours: values.durationHours ? Number(values.durationHours) : undefined,
      // an internship course has no price of its own; a regular course keeps the price field exactly as before
      price: internship ? 0 : values.price ? Number(values.price) : undefined,
      course_type: values.courseType,
      show_internship_fee: internship ? values.showInternshipFee : false,
    };

    if (isEditing) {
      updateCourse.mutate({ ...shared, title: values.title }, { onSuccess: () => onOpenChange(false) });
      return;
    }
    createCourse.mutate(
      { ...shared, title: values.title, slug: values.slug },
      {
        onSuccess: async (created) => {
          if (!internship || !internshipId) {
            finish();
            return;
          }
          setLinking(true);
          try {
            await onboardingApi.setCourse(internshipId, created.id, replace);
            finish(created.id);
          } catch (e) {
            setPartial({ courseId: created.id, message: errorMessage(e, "The internship could not be linked.") });
          } finally {
            setLinking(false);
            void queryClient.invalidateQueries({ queryKey: ourInternshipsKeys.all });
            void queryClient.invalidateQueries({ queryKey: ["courses"] });
          }
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit course" : "New course"}</DialogTitle>
        </DialogHeader>
        {partial ? (
          <div className="space-y-4">
            <p className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200" role="alert">
              The course was created, but it was <strong>not linked</strong> to the internship: {partial.message}
            </p>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Close
              </Button>
              <Button type="button" onClick={() => (onOpenChange(false), navigate(`/courses/${partial.courseId}`))}>
                Open the course
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="courseType">Course type</Label>
              <select
                id="courseType"
                className={selectClass}
                disabled={isEditing && course?.course_type === "internship" && linkedCount > 0}
                {...register("courseType", {
                  onChange: (e) => {
                    if (e.target.value === "regular") setValue("showInternshipFee", false);
                    if (e.target.value === "internship") setValue("price", "");
                  },
                })}
              >
                {courseTypeValues.map((t) => (
                  <option key={t} value={t}>
                    {courseTypeLabels[t]}
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground">
                {isInternship
                  ? "Part of an internship. Its fee is the internship's, set in its onboarding settings; the course has no price of its own."
                  : "A standalone course with its own price."}
                {isEditing && course?.course_type === "internship" && linkedCount > 0 && " Linked to an internship: unlink it before making it a regular course."}
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            {!isEditing && (
              <div className="space-y-2">
                <Label htmlFor="slug">Slug</Label>
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
                <Label htmlFor="level">Level</Label>
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
              {!isInternship ? (
                <div className="space-y-2">
                  <Label htmlFor="price">Price</Label>
                  <Input id="price" type="number" step="0.01" {...register("price")} />
                  {errors.price && <p className="text-sm text-destructive">{errors.price.message}</p>}
                </div>
              ) : (
                <div className="space-y-2">
                  <Label htmlFor="showInternshipFee">Fee visibility</Label>
                  <select
                    id="showInternshipFee"
                    className={selectClass}
                    value={showFee ? "show" : "hide"}
                    onChange={(e) => setValue("showInternshipFee", e.target.value === "show")}
                  >
                    <option value="hide">Hide Fee</option>
                    <option value="show">Show Fee</option>
                  </select>
                </div>
              )}
            </div>
            {isInternship && (
              <p className="text-xs text-muted-foreground">
                Show Fee displays the linked internship's own fee (from its onboarding settings) to staff who may see finance. Hide Fee shows no price or fee.
                Students still pay through the internship's normal onboarding.
              </p>
            )}
            <div className="space-y-2">
              <Label htmlFor="thumbnailUrl">Thumbnail URL</Label>
              <Input id="thumbnailUrl" {...register("thumbnailUrl")} />
            </div>

            {isInternship && !isEditing && (
              <div className="space-y-2 rounded-md border p-3">
                <Label htmlFor="linkInternship">Internship</Label>
                <InternshipPicker id="linkInternship" value={internshipId} onChange={(v) => (setInternshipId(v), setReplace(false))} />
                <p className="text-xs text-muted-foreground">Optional. You can also link it later from the course or from the internship's Onboarding Settings.</p>
                {replacing && (
                  <label className="flex items-start gap-2 rounded-md bg-amber-50 p-2 text-sm text-amber-900 dark:bg-amber-500/10 dark:text-amber-200">
                    <input type="checkbox" className="mt-1" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
                    <span>
                      This internship already uses <strong>{selected?.lms_course_title}</strong>. Replace it with this course. (This is refused if students already
                      have access through it.)
                    </span>
                  </label>
                )}
              </div>
            )}

            {mutation.isError && (
              <p className="text-sm text-destructive" role="alert">
                {errorMessage(mutation.error, "Something went wrong. Please try again.")}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending || linking || (replacing && !replace && isInternship && !isEditing)}>
                {mutation.isPending || linking ? "Saving..." : isEditing ? "Save changes" : "Create course"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronDown, ChevronRight, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ResourcesPanel } from "@/features/courses/resources/components/resources-panel";
import {
  useCreateLesson,
  useDeleteLesson,
  useLessons,
} from "@/features/courses/lessons/api/lessons-hooks";
import {
  type LessonFormValues,
  lessonContentTypeLabels,
  lessonContentTypeValues,
  lessonFormSchema,
} from "@/features/courses/lessons/schemas/lesson-schemas";

interface LessonsPanelProps {
  courseId: string;
  chapterId: string;
}

export function LessonsPanel({ courseId, chapterId }: LessonsPanelProps) {
  const { data: lessons, isLoading } = useLessons(courseId, chapterId);
  const createLesson = useCreateLesson(courseId, chapterId);
  const deleteLesson = useDeleteLesson(courseId, chapterId);
  const [formOpen, setFormOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<LessonFormValues>({
    resolver: zodResolver(lessonFormSchema),
    defaultValues: {
      title: "",
      contentType: "video",
      videoUrl: "",
      contentText: "",
      durationMinutes: "",
      orderIndex: String((lessons?.length ?? 0) + 1),
      isPreview: false,
    },
  });

  const contentType = watch("contentType");

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onSubmit = (values: LessonFormValues) => {
    createLesson.mutate(
      {
        title: values.title,
        content_type: values.contentType,
        video_url: values.videoUrl || undefined,
        content_text: values.contentText || undefined,
        duration_minutes: values.durationMinutes ? Number(values.durationMinutes) : undefined,
        order_index: Number(values.orderIndex),
        is_preview: values.isPreview,
      },
      {
        onSuccess: () => {
          setFormOpen(false);
          reset();
        },
      }
    );
  };

  return (
    <div className="space-y-2 pl-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Lessons
        </p>
        <Button variant="ghost" size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-3 w-3" />
          Add lesson
        </Button>
      </div>

      {isLoading && <Skeleton className="h-8 w-full" />}
      {!isLoading && (lessons?.length ?? 0) === 0 && (
        <p className="text-xs text-muted-foreground">No lessons yet.</p>
      )}

      <div className="space-y-2">
        {lessons?.map((lesson) => (
          <div key={lesson.id} className="rounded-md border p-2">
            <div className="flex items-center justify-between">
              <button
                type="button"
                className="flex flex-1 items-center gap-2 text-left"
                onClick={() => toggle(lesson.id)}
              >
                {expanded.has(lesson.id) ? (
                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                )}
                <span className="text-sm font-medium">{lesson.title}</span>
                <Badge variant="outline">{lessonContentTypeLabels[lesson.content_type]}</Badge>
                {lesson.is_preview && <Badge variant="info">Preview</Badge>}
                {lesson.duration_minutes && (
                  <span className="text-xs text-muted-foreground">
                    {lesson.duration_minutes} min
                  </span>
                )}
              </button>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => deleteLesson.mutate(lesson.id)}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
            {expanded.has(lesson.id) && (
              <div className="mt-2">
                <ResourcesPanel courseId={courseId} chapterId={chapterId} lessonId={lesson.id} />
              </div>
            )}
          </div>
        ))}
      </div>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add lesson</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="contentType">Content type</Label>
                <Controller
                  control={control}
                  name="contentType"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="contentType">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {lessonContentTypeValues.map((t) => (
                          <SelectItem key={t} value={t}>
                            {lessonContentTypeLabels[t]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="orderIndex">Order</Label>
                <Input id="orderIndex" type="number" {...register("orderIndex")} />
                {errors.orderIndex && (
                  <p className="text-sm text-destructive">{errors.orderIndex.message}</p>
                )}
              </div>
            </div>
            {contentType === "video" && (
              <div className="space-y-2">
                <Label htmlFor="videoUrl">Video URL</Label>
                <Input id="videoUrl" {...register("videoUrl")} />
              </div>
            )}
            {(contentType === "text" || contentType === "quiz") && (
              <div className="space-y-2">
                <Label htmlFor="contentText">Content</Label>
                <Textarea id="contentText" rows={4} {...register("contentText")} />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="durationMinutes">Duration (minutes)</Label>
              <Input id="durationMinutes" type="number" {...register("durationMinutes")} />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="h-4 w-4 rounded border-input" {...register("isPreview")} />
              Available as free preview
            </label>
            {createLesson.isError && (
              <p className="text-sm text-destructive">
                {(createLesson.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createLesson.isPending}>
                {createLesson.isPending ? "Saving..." : "Add lesson"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

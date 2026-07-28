import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronDown, ChevronRight, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useChapters, useCreateChapter, useDeleteChapter } from "@/features/courses/chapters/api/chapters-hooks";
import {
  type ChapterFormValues,
  chapterFormSchema,
} from "@/features/courses/chapters/schemas/chapter-schemas";
import { LessonsPanel } from "@/features/courses/lessons/components/lessons-panel";

export function ChaptersPanel({ courseId }: { courseId: string }) {
  const { data: chapters, isLoading } = useChapters(courseId);
  const createChapter = useCreateChapter(courseId);
  const deleteChapter = useDeleteChapter(courseId);
  const [formOpen, setFormOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ChapterFormValues>({
    resolver: zodResolver(chapterFormSchema),
    defaultValues: { title: "", description: "", orderIndex: String((chapters?.length ?? 0) + 1) },
  });

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onSubmit = (values: ChapterFormValues) => {
    createChapter.mutate(
      {
        title: values.title,
        description: values.description || undefined,
        order_index: Number(values.orderIndex),
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
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Curriculum</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Add chapter
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (chapters?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">
            No chapters yet. Add a chapter to start building the curriculum.
          </p>
        )}
        {chapters?.map((chapter) => (
          <div key={chapter.id} className="rounded-md border p-3">
            <div className="flex items-center justify-between">
              <button
                type="button"
                className="flex flex-1 items-center gap-2 text-left"
                onClick={() => toggle(chapter.id)}
              >
                {expanded.has(chapter.id) ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                <span className="text-sm font-medium">
                  {chapter.order_index}. {chapter.title}
                </span>
              </button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => deleteChapter.mutate(chapter.id)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
            {chapter.description && (
              <p className="mt-1 pl-6 text-xs text-muted-foreground">{chapter.description}</p>
            )}
            {expanded.has(chapter.id) && (
              <div className="mt-3">
                <LessonsPanel courseId={courseId} chapterId={chapter.id} />
              </div>
            )}
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add chapter</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="orderIndex">Order</Label>
              <Input id="orderIndex" type="number" {...register("orderIndex")} />
              {errors.orderIndex && (
                <p className="text-sm text-destructive">{errors.orderIndex.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" rows={3} {...register("description")} />
            </div>
            {createChapter.isError && (
              <p className="text-sm text-destructive">
                {(createChapter.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createChapter.isPending}>
                {createChapter.isPending ? "Saving..." : "Add chapter"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import {
  useCreateLearningPath,
  useDeleteLearningPath,
  useLearningPaths,
} from "@/features/courses/learning-paths/api/learning-paths-hooks";
import {
  type LearningPathFormValues,
  learningPathFormSchema,
} from "@/features/courses/learning-paths/schemas/learning-path-schemas";

export function LearningPathsListPage() {
  const navigate = useNavigate();
  const { data: paths, isLoading, isError } = useLearningPaths();
  const createPath = useCreateLearningPath();
  const deletePath = useDeleteLearningPath();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<LearningPathFormValues>({ resolver: zodResolver(learningPathFormSchema) });

  const onSubmit = (values: LearningPathFormValues) => {
    createPath.mutate(
      { title: values.title, slug: values.slug, description: values.description || undefined },
      {
        onSuccess: () => {
          setFormOpen(false);
          reset();
        },
      }
    );
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Learning Paths</h1>
          <p className="mt-1 text-muted-foreground">
            Group courses into a guided, sequential learning journey.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Learning Path
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-3 p-6">
          {isLoading && <Skeleton className="h-24 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load learning paths.
            </p>
          )}
          {!isLoading && !isError && (paths?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No learning paths yet. Create one to group courses into a journey.
            </p>
          )}
          {paths?.map((path) => (
            <div
              key={path.id}
              role="button"
              tabIndex={0}
              className="flex cursor-pointer items-center justify-between rounded-md border p-3"
              onClick={() => navigate(`/courses/learning-paths/${path.id}`)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  navigate(`/courses/learning-paths/${path.id}`);
                }
              }}
            >
              <div>
                <p className="text-sm font-medium">{path.title}</p>
                <p className="text-xs text-muted-foreground">{path.slug}</p>
                {path.description && (
                  <p className="mt-1 text-xs text-muted-foreground">{path.description}</p>
                )}
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={(e) => {
                  e.stopPropagation();
                  deletePath.mutate(path.id);
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New learning path</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="slug">Slug</Label>
              <Input id="slug" placeholder="e.g. become-a-web-developer" {...register("slug")} />
              {errors.slug && <p className="text-sm text-destructive">{errors.slug.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" rows={3} {...register("description")} />
            </div>
            {createPath.isError && (
              <p className="text-sm text-destructive">
                {(createPath.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createPath.isPending}>
                {createPath.isPending ? "Saving..." : "Create path"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

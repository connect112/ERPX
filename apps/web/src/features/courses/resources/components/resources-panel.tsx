import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
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
import {
  useCreateResource,
  useDeleteResource,
  useResources,
} from "@/features/courses/resources/api/resources-hooks";
import {
  type ResourceFormValues,
  resourceFormSchema,
  resourceTypeLabels,
  resourceTypeValues,
} from "@/features/courses/resources/schemas/resource-schemas";

interface ResourcesPanelProps {
  courseId: string;
  chapterId: string;
  lessonId: string;
}

export function ResourcesPanel({ courseId, chapterId, lessonId }: ResourcesPanelProps) {
  const { data: resources, isLoading } = useResources(courseId, chapterId, lessonId);
  const createResource = useCreateResource(courseId, chapterId, lessonId);
  const deleteResource = useDeleteResource(courseId, chapterId, lessonId);
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ResourceFormValues>({
    resolver: zodResolver(resourceFormSchema),
    defaultValues: { title: "", resourceType: "other", fileUrl: "", isDownloadable: true },
  });

  const onSubmit = (values: ResourceFormValues) => {
    createResource.mutate(
      {
        title: values.title,
        resource_type: values.resourceType,
        file_url: values.fileUrl,
        is_downloadable: values.isDownloadable,
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
    <div className="space-y-2 rounded-md border border-dashed p-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Resources
        </p>
        <Button variant="ghost" size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-3 w-3" />
          Add resource
        </Button>
      </div>

      {isLoading && <Skeleton className="h-8 w-full" />}
      {!isLoading && (resources?.length ?? 0) === 0 && (
        <p className="text-xs text-muted-foreground">No resources attached.</p>
      )}
      {resources?.map((resource) => (
        <div key={resource.id} className="flex items-center justify-between rounded border px-2 py-1.5">
          <div className="flex items-center gap-2">
            <Badge variant="outline">{resourceTypeLabels[resource.resource_type]}</Badge>
            <a
              href={resource.file_url}
              target="_blank"
              rel="noreferrer"
              className="text-xs font-medium text-primary hover:underline"
            >
              {resource.title}
            </a>
            {!resource.is_downloadable && (
              <span className="text-[10px] text-muted-foreground">(view only)</span>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => deleteResource.mutate(resource.id)}
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      ))}

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add resource</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title" required>Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="resourceType" required>Type</Label>
              <Controller
                control={control}
                name="resourceType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="resourceType">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {resourceTypeValues.map((t) => (
                        <SelectItem key={t} value={t}>
                          {resourceTypeLabels[t]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fileUrl" required>File URL</Label>
              <Input id="fileUrl" {...register("fileUrl")} />
              {errors.fileUrl && (
                <p className="text-sm text-destructive">{errors.fileUrl.message}</p>
              )}
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="h-4 w-4 rounded border-input" {...register("isDownloadable")} />
              Downloadable
            </label>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createResource.isPending}>
                {createResource.isPending ? "Saving..." : "Add resource"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

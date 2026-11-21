import { zodResolver } from "@hookform/resolvers/zod";
import { Download, Plus, Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useCurriculumAccess } from "@/features/courses/lib/curriculum-access";
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
  useUploadResource,
} from "@/features/courses/resources/api/resources-hooks";
import { resourcesApi } from "@/features/courses/resources/api/resources-api";
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
  const { canManage } = useCurriculumAccess();
  const deleteResource = useDeleteResource(courseId, chapterId, lessonId);
  const uploadResource = useUploadResource(courseId, chapterId, lessonId);
  const [formOpen, setFormOpen] = useState(false);
  // a file is the normal way to add a resource; a link is for something that lives elsewhere
  const [mode, setMode] = useState<"upload" | "link">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const download = async (resourceId: string) => {
    setDownloadError(null);
    try {
      const { url } = await resourcesApi.downloadLink(courseId, chapterId, lessonId, resourceId);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch {
      setDownloadError("You cannot download this file.");
    }
  };

  const {
    register,
    control,
    handleSubmit,
    reset,
    getValues,
    formState: { errors },
  } = useForm<ResourceFormValues>({
    resolver: zodResolver(resourceFormSchema),
    defaultValues: { title: "", resourceType: "other", fileUrl: "", isDownloadable: true },
  });

  const onUpload = (values: ResourceFormValues) => {
    if (values.title.trim().length < 2) {
      setUploadError("Give the resource a title.");
      return;
    }
    if (!file) {
      setUploadError("Choose a file to upload.");
      return;
    }
    setUploadError(null);
    uploadResource.mutate(
      { file, title: values.title, resourceType: values.resourceType, isDownloadable: values.isDownloadable },
      {
        onSuccess: () => {
          setFormOpen(false);
          setFile(null);
          reset();
        },
        onError: (error) => {
          const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message;
          setUploadError(message ?? "The file could not be uploaded.");
        },
      },
    );
  };

  const onSubmit = (values: ResourceFormValues) => {
    if (mode === "upload") return onUpload(values);
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
        {canManage && (
          <Button variant="ghost" size="sm" onClick={() => setFormOpen(true)}>
            <Plus className="h-3 w-3" />
            Add resource
          </Button>
        )}
      </div>

      {downloadError && <p className="text-xs text-destructive">{downloadError}</p>}
      {isLoading && <Skeleton className="h-8 w-full" />}
      {!isLoading && (resources?.length ?? 0) === 0 && (
        <p className="text-xs text-muted-foreground">No resources attached.</p>
      )}
      {resources?.map((resource) => (
        <div key={resource.id} className="flex items-center justify-between rounded border px-2 py-1.5">
          <div className="flex items-center gap-2">
            <Badge variant="outline">{resourceTypeLabels[resource.resource_type]}</Badge>
            {resource.is_upload ? (
              <button type="button" onClick={() => void download(resource.id)} className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline" data-testid={`download-${resource.title}`}>
                <Download className="h-3 w-3" />
                {resource.title}
                <span className="font-normal text-muted-foreground">
                  ({resource.original_filename}
                  {resource.size_bytes != null ? `, ${resource.size_bytes < 1024 * 1024 ? `${Math.max(1, Math.round(resource.size_bytes / 1024))} KB` : `${(resource.size_bytes / (1024 * 1024)).toFixed(1)} MB`}` : ""})
                </span>
              </button>
            ) : (
              <a
                href={resource.file_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs font-medium text-primary hover:underline"
              >
                {resource.title}
              </a>
            )}
            {!resource.is_downloadable && (
              <span className="text-[10px] text-muted-foreground">(view only)</span>
            )}
          </div>
          {canManage && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              aria-label={`Delete resource ${resource.title}`}
              onClick={() => deleteResource.mutate(resource.id)}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          )}
        </div>
      ))}

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add resource</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit, () => { if (mode === "upload") onUpload(getValues()); })} className="space-y-4">
            <div className="flex gap-2" role="radiogroup" aria-label="How to add it">
              <Button type="button" size="sm" variant={mode === "upload" ? "default" : "outline"} onClick={() => setMode("upload")} role="radio" aria-checked={mode === "upload"}>
                <Upload className="h-3 w-3" />
                Upload a file
              </Button>
              <Button type="button" size="sm" variant={mode === "link" ? "default" : "outline"} onClick={() => setMode("link")} role="radio" aria-checked={mode === "link"}>
                Link
              </Button>
            </div>
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="resourceType">Type</Label>
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
            {mode === "link" ? (
              <div className="space-y-2">
                <Label htmlFor="fileUrl">File URL</Label>
                <Input id="fileUrl" {...register("fileUrl")} />
                {errors.fileUrl && (
                  <p className="text-sm text-destructive">{errors.fileUrl.message}</p>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="resourceFile">File</Label>
                <Input id="resourceFile" type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                <p className="text-xs text-muted-foreground">Up to 25 MB. Programs and web pages cannot be uploaded.</p>
                {uploadError && <p role="alert" className="text-sm text-destructive">{uploadError}</p>}
              </div>
            )}
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="h-4 w-4 rounded border-input" {...register("isDownloadable")} />
              Downloadable
            </label>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createResource.isPending || uploadResource.isPending}>
                {createResource.isPending || uploadResource.isPending ? "Saving..." : mode === "upload" ? "Upload" : "Add resource"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

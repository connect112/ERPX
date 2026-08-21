import { zodResolver } from "@hookform/resolvers/zod";
import { Megaphone, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useCoursesList } from "@/features/courses/api/courses-hooks";
import {
  useAnnouncements,
  useCreateAnnouncement,
  useDeleteAnnouncement,
} from "@/features/lms/announcements/api/announcements-hooks";
import {
  type AnnouncementFormValues,
  announcementFormSchema,
} from "@/features/lms/announcements/schemas/announcement-schemas";

export function AnnouncementsListPage() {
  const { data: courses } = useCoursesList({ limit: 200 });
  const { data: announcements, isLoading, isError } = useAnnouncements();
  const createAnnouncement = useCreateAnnouncement();
  const deleteAnnouncement = useDeleteAnnouncement();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AnnouncementFormValues>({ resolver: zodResolver(announcementFormSchema) });

  const courseTitle = (id: string | null) =>
    id ? (courses?.items.find((c) => c.id === id)?.title ?? id) : "Organization-wide";

  const onSubmit = (values: AnnouncementFormValues) => {
    createAnnouncement.mutate(
      { course_id: values.courseId || undefined, title: values.title, body: values.body },
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
          <h1 className="text-2xl font-semibold tracking-tight">Announcements</h1>
          <p className="mt-1 text-muted-foreground">
            Broadcast updates organization-wide or to a specific course.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Announcement
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-3 p-6">
          {isLoading && <Skeleton className="h-24 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load announcements.
            </p>
          )}
          {!isLoading && !isError && (announcements?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No announcements yet.
            </p>
          )}
          {announcements?.map((announcement) => (
            <div key={announcement.id} className="rounded-md border p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-start gap-2">
                  <Megaphone className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <div>
                    <p className="text-sm font-medium">{announcement.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {courseTitle(announcement.course_id)} ·{" "}
                      {new Date(announcement.published_at).toLocaleDateString()}
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">{announcement.body}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => deleteAnnouncement.mutate(announcement.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New announcement</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="courseId">Course (optional)</Label>
              <Controller
                control={control}
                name="courseId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="courseId">
                      <SelectValue placeholder="Organization-wide" />
                    </SelectTrigger>
                    <SelectContent>
                      {courses?.items.map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.title}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="title" required>Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="body" required>Body</Label>
              <Textarea id="body" rows={4} {...register("body")} />
              {errors.body && <p className="text-sm text-destructive">{errors.body.message}</p>}
            </div>
            {createAnnouncement.isError && (
              <p className="text-sm text-destructive">
                {(createAnnouncement.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createAnnouncement.isPending}>
                {createAnnouncement.isPending ? "Posting..." : "Post announcement"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

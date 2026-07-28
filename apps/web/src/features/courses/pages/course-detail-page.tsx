import { ArrowLeft, Pencil, Trash2 } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCategories } from "@/features/courses/categories/api/categories-hooks";
import { useCourse, useDeleteCourse, useTogglePublishCourse } from "@/features/courses/api/courses-hooks";
import { ChaptersPanel } from "@/features/courses/chapters/components/chapters-panel";
import { CourseFormDialog } from "@/features/courses/components/course-form-dialog";
import { CourseStatusBadge } from "@/features/courses/components/course-status-badge";
import { courseLevelLabels } from "@/features/courses/schemas/course-schemas";
import { ExamsPanel } from "@/features/examinations/exams/components/exams-panel";
import { PracticalsPanel } from "@/features/examinations/practicals/components/practicals-panel";
import { VivaPanel } from "@/features/examinations/viva/components/viva-panel";
import { AssessmentsPanel } from "@/features/lms/assessments/components/assessments-panel";
import { AssignmentsPanel } from "@/features/lms/assignments/components/assignments-panel";
import { DiscussionsPanel } from "@/features/lms/discussions/components/discussions-panel";
import { EnrollmentsByCoursePanel } from "@/features/lms/enrollment/components/enrollments-by-course-panel";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function CourseDetailPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const { data: course, isLoading } = useCourse(courseId);
  const { data: categories } = useCategories();
  const togglePublish = useTogglePublishCourse(courseId ?? "");
  const deleteCourse = useDeleteCourse();

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  if (isLoading || !course) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const categoryName = categories?.find((c) => c.id === course.category_id)?.name ?? "—";

  const handleDelete = () => {
    deleteCourse.mutate(course.id, { onSuccess: () => navigate("/courses") });
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/courses")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{course.title}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">{course.slug}</span>
              <CourseStatusBadge isPublished={course.is_published} />
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => togglePublish.mutate(!course.is_published)}
            disabled={togglePublish.isPending}
          >
            {course.is_published ? "Unpublish" : "Publish"}
          </Button>
          <Button variant="outline" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4" />
            Edit
          </Button>
          <Button variant="outline" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Course details</CardTitle>
          </CardHeader>
          <CardContent>
            {course.short_description && (
              <p className="pb-3 text-sm text-muted-foreground">{course.short_description}</p>
            )}
            <DetailRow label="Category" value={categoryName} />
            <DetailRow label="Level" value={courseLevelLabels[course.level]} />
            <DetailRow
              label="Duration"
              value={course.duration_hours ? `${course.duration_hours} hours` : "—"}
            />
            <DetailRow label="Price" value={course.price > 0 ? `₹${course.price}` : "Free"} />
            {course.description && (
              <div className="pt-3">
                <p className="text-sm text-muted-foreground">Description</p>
                <p className="mt-1 whitespace-pre-wrap text-sm">{course.description}</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Thumbnail</CardTitle>
          </CardHeader>
          <CardContent>
            {course.thumbnail_url ? (
              <img
                src={course.thumbnail_url}
                alt={course.title}
                className="aspect-video w-full rounded-md object-cover"
              />
            ) : (
              <p className="text-sm text-muted-foreground">No thumbnail set.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="curriculum">
        <div className="overflow-x-auto">
          <TabsList>
            <TabsTrigger value="curriculum">Curriculum</TabsTrigger>
            <TabsTrigger value="enrollments">Enrollments</TabsTrigger>
            <TabsTrigger value="assignments">Assignments</TabsTrigger>
            <TabsTrigger value="assessments">Assessments</TabsTrigger>
            <TabsTrigger value="discussions">Discussions</TabsTrigger>
            <TabsTrigger value="exams">Exams</TabsTrigger>
            <TabsTrigger value="practicals">Practicals</TabsTrigger>
            <TabsTrigger value="viva">Viva</TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="curriculum">
          <ChaptersPanel courseId={course.id} />
        </TabsContent>
        <TabsContent value="enrollments">
          <EnrollmentsByCoursePanel courseId={course.id} />
        </TabsContent>
        <TabsContent value="assignments">
          <AssignmentsPanel courseId={course.id} />
        </TabsContent>
        <TabsContent value="assessments">
          <AssessmentsPanel courseId={course.id} />
        </TabsContent>
        <TabsContent value="discussions">
          <DiscussionsPanel courseId={course.id} />
        </TabsContent>
        <TabsContent value="exams">
          <ExamsPanel courseId={course.id} />
        </TabsContent>
        <TabsContent value="practicals">
          <PracticalsPanel courseId={course.id} />
        </TabsContent>
        <TabsContent value="viva">
          <VivaPanel courseId={course.id} />
        </TabsContent>
      </Tabs>

      <CourseFormDialog open={editOpen} onOpenChange={setEditOpen} course={course} />

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete course</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete <span className="font-medium">{course.title}</span>?
            This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteCourse.isPending}>
              {deleteCourse.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

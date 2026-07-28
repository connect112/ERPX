import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronDown, ChevronRight, Plus } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { Badge, type BadgeProps } from "@/components/ui/badge";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useCoursesList } from "@/features/courses/api/courses-hooks";
import {
  useChangeEnrollmentStatus,
  useCreateEnrollment,
  useEnrollmentsForStudent,
} from "@/features/lms/enrollment/api/enrollment-hooks";
import {
  type EnrollInCourseFormValues,
  type EnrollmentStatus,
  enrollInCourseFormSchema,
  enrollmentStatusLabels,
  enrollmentStatusValues,
} from "@/features/lms/enrollment/schemas/enrollment-schemas";
import { CourseProgressView } from "@/features/lms/progress/components/course-progress-view";

const statusVariant: Record<EnrollmentStatus, BadgeProps["variant"]> = {
  active: "info",
  completed: "success",
  dropped: "destructive",
};

export function EnrollmentsByStudentPanel({ studentId }: { studentId: string }) {
  const { data: enrollments, isLoading } = useEnrollmentsForStudent(studentId);
  const { data: courses } = useCoursesList({ limit: 200 });
  const createEnrollment = useCreateEnrollment();
  const changeStatus = useChangeEnrollmentStatus();
  const [formOpen, setFormOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EnrollInCourseFormValues>({ resolver: zodResolver(enrollInCourseFormSchema) });

  const courseTitle = (id: string) => courses?.items.find((c) => c.id === id)?.title ?? id;

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onSubmit = (values: EnrollInCourseFormValues) => {
    createEnrollment.mutate(
      { student_id: studentId, course_id: values.courseId, enrolled_on: values.enrolledOn || undefined },
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
        <CardTitle className="text-base">Enrollments</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Enroll in course
        </Button>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (enrollments?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">Not enrolled in any courses yet.</p>
        )}
        {enrollments?.map((enrollment) => (
          <div key={enrollment.id} className="rounded-md border p-3">
            <div className="flex items-center justify-between">
              <button
                type="button"
                className="flex flex-1 items-center gap-2 text-left"
                onClick={() => toggle(enrollment.id)}
              >
                {expanded.has(enrollment.id) ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                <span className="text-sm font-medium">{courseTitle(enrollment.course_id)}</span>
              </button>
              <Select
                value={enrollment.status}
                onValueChange={(status) =>
                  changeStatus.mutate({ id: enrollment.id, status: status as EnrollmentStatus })
                }
              >
                <SelectTrigger className="h-8 w-36 text-xs">
                  <SelectValue>
                    <Badge variant={statusVariant[enrollment.status]}>
                      {enrollmentStatusLabels[enrollment.status]}
                    </Badge>
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {enrollmentStatusValues.map((s) => (
                    <SelectItem key={s} value={s}>
                      {enrollmentStatusLabels[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {expanded.has(enrollment.id) && (
              <div className="mt-3 pl-6">
                <CourseProgressView studentId={studentId} courseId={enrollment.course_id} />
              </div>
            )}
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enroll in course</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="courseId">Course</Label>
              <Controller
                control={control}
                name="courseId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="courseId">
                      <SelectValue placeholder="Select a course" />
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
              {errors.courseId && (
                <p className="text-sm text-destructive">{errors.courseId.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="enrolledOn">Enrolled on</Label>
              <Input id="enrolledOn" type="date" {...register("enrolledOn")} />
            </div>
            {createEnrollment.isError && (
              <p className="text-sm text-destructive">
                {(createEnrollment.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createEnrollment.isPending}>
                {createEnrollment.isPending ? "Enrolling..." : "Enroll"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

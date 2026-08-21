import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
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
import { useStudentsList } from "@/features/students/api/students-hooks";
import {
  useChangeEnrollmentStatus,
  useCreateEnrollment,
  useEnrollmentsForCourse,
} from "@/features/lms/enrollment/api/enrollment-hooks";
import {
  type EnrollFormValues,
  type EnrollmentStatus,
  enrollFormSchema,
  enrollmentStatusLabels,
  enrollmentStatusValues,
} from "@/features/lms/enrollment/schemas/enrollment-schemas";

const statusVariant: Record<EnrollmentStatus, BadgeProps["variant"]> = {
  active: "info",
  completed: "success",
  dropped: "destructive",
};

export function EnrollmentsByCoursePanel({ courseId }: { courseId: string }) {
  const { data: enrollments, isLoading } = useEnrollmentsForCourse(courseId);
  const { data: students } = useStudentsList({ limit: 200 });
  const createEnrollment = useCreateEnrollment();
  const changeStatus = useChangeEnrollmentStatus();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EnrollFormValues>({ resolver: zodResolver(enrollFormSchema) });

  const studentName = (id: string) => students?.items.find((s) => s.id === id)?.full_name ?? id;

  const onSubmit = (values: EnrollFormValues) => {
    createEnrollment.mutate(
      { student_id: values.studentId, course_id: courseId, enrolled_on: values.enrolledOn || undefined },
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
          Enroll student
        </Button>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (enrollments?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No students enrolled yet.</p>
        )}
        {enrollments?.map((enrollment) => (
          <div key={enrollment.id} className="flex items-center justify-between rounded-md border p-3">
            <div>
              <p className="text-sm font-medium">{studentName(enrollment.student_id)}</p>
              <p className="text-xs text-muted-foreground">
                Enrolled {new Date(enrollment.enrolled_on).toLocaleDateString()}
              </p>
            </div>
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
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enroll student</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="studentId" required>Student</Label>
              <Controller
                control={control}
                name="studentId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="studentId">
                      <SelectValue placeholder="Select a student" />
                    </SelectTrigger>
                    <SelectContent>
                      {students?.items.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.full_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.studentId && (
                <p className="text-sm text-destructive">{errors.studentId.message}</p>
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

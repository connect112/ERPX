import { z } from "zod";

export const enrollmentStatusValues = ["active", "completed", "dropped"] as const;
export type EnrollmentStatus = (typeof enrollmentStatusValues)[number];

export const enrollmentStatusLabels: Record<EnrollmentStatus, string> = {
  active: "Active",
  completed: "Completed",
  dropped: "Dropped",
};

export const enrollFormSchema = z.object({
  studentId: z.string().min(1, "Select a student."),
  enrolledOn: z.string().optional().or(z.literal("")),
});
export type EnrollFormValues = z.infer<typeof enrollFormSchema>;

export const enrollInCourseFormSchema = z.object({
  courseId: z.string().min(1, "Select a course."),
  enrolledOn: z.string().optional().or(z.literal("")),
});
export type EnrollInCourseFormValues = z.infer<typeof enrollInCourseFormSchema>;

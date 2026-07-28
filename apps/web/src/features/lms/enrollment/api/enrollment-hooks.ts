import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type EnrollmentCreatePayload,
  enrollmentApi,
} from "@/features/lms/enrollment/api/enrollment-api";
import type { EnrollmentStatus } from "@/features/lms/enrollment/schemas/enrollment-schemas";

const byStudentKey = (studentId: string) => ["lms", "enrollment", "by-student", studentId] as const;
const byCourseKey = (courseId: string) => ["lms", "enrollment", "by-course", courseId] as const;

export function useEnrollmentsForStudent(studentId: string) {
  return useQuery({
    queryKey: byStudentKey(studentId),
    queryFn: () => enrollmentApi.listForStudent(studentId),
    enabled: !!studentId,
  });
}

export function useEnrollmentsForCourse(courseId: string) {
  return useQuery({
    queryKey: byCourseKey(courseId),
    queryFn: () => enrollmentApi.listForCourse(courseId),
    enabled: !!courseId,
  });
}

export function useCreateEnrollment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: EnrollmentCreatePayload) => enrollmentApi.create(payload),
    onSuccess: (enrollment) => {
      queryClient.invalidateQueries({ queryKey: byStudentKey(enrollment.student_id) });
      queryClient.invalidateQueries({ queryKey: byCourseKey(enrollment.course_id) });
    },
  });
}

export function useChangeEnrollmentStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: EnrollmentStatus }) =>
      enrollmentApi.changeStatus(id, status),
    onSuccess: (enrollment) => {
      queryClient.invalidateQueries({ queryKey: byStudentKey(enrollment.student_id) });
      queryClient.invalidateQueries({ queryKey: byCourseKey(enrollment.course_id) });
    },
  });
}

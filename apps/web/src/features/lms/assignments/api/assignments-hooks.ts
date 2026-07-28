import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AssignmentCreatePayload,
  type AssignmentUpdatePayload,
  type SubmissionCreatePayload,
  type SubmissionGradePayload,
  assignmentsApi,
} from "@/features/lms/assignments/api/assignments-api";

const assignmentsKey = (courseId: string) => ["lms", "assignments", courseId] as const;
const submissionsKey = (courseId: string, assignmentId: string) =>
  [...assignmentsKey(courseId), assignmentId, "submissions"] as const;

export function useAssignments(courseId: string) {
  return useQuery({
    queryKey: assignmentsKey(courseId),
    queryFn: () => assignmentsApi.list(courseId),
    enabled: !!courseId,
  });
}

export function useCreateAssignment(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AssignmentCreatePayload) => assignmentsApi.create(courseId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentsKey(courseId) }),
  });
}

export function useUpdateAssignment(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      assignmentId,
      payload,
    }: {
      assignmentId: string;
      payload: AssignmentUpdatePayload;
    }) => assignmentsApi.update(courseId, assignmentId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentsKey(courseId) }),
  });
}

export function useDeleteAssignment(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) => assignmentsApi.remove(courseId, assignmentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentsKey(courseId) }),
  });
}

export function useSubmissions(courseId: string, assignmentId: string) {
  return useQuery({
    queryKey: submissionsKey(courseId, assignmentId),
    queryFn: () => assignmentsApi.listSubmissions(courseId, assignmentId),
    enabled: !!courseId && !!assignmentId,
  });
}

export function useSubmitAssignment(courseId: string, assignmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SubmissionCreatePayload) =>
      assignmentsApi.submit(courseId, assignmentId, payload),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: submissionsKey(courseId, assignmentId) }),
  });
}

export function useGradeSubmission(courseId: string, assignmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      submissionId,
      payload,
    }: {
      submissionId: string;
      payload: SubmissionGradePayload;
    }) => assignmentsApi.grade(courseId, assignmentId, submissionId, payload),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: submissionsKey(courseId, assignmentId) }),
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { assignmentsApi, type MySubmissionPayload } from "@/features/lms/assignments/api/assignments-api";

const assignmentsKey = (courseId: string) => ["lms", "assignments", courseId] as const;
const mySubmissionKey = (courseId: string, assignmentId: string) =>
  [...assignmentsKey(courseId), assignmentId, "submission", "mine"] as const;

export function useCourseAssignments(courseId: string | undefined) {
  return useQuery({
    queryKey: assignmentsKey(courseId as string),
    queryFn: () => assignmentsApi.list(courseId as string),
    enabled: Boolean(courseId),
  });
}

export function useMySubmission(courseId: string | undefined, assignmentId: string) {
  return useQuery({
    queryKey: mySubmissionKey(courseId as string, assignmentId),
    queryFn: () => assignmentsApi.mySubmission(courseId as string, assignmentId),
    enabled: Boolean(courseId),
  });
}

export function useSubmitAssignment(courseId: string | undefined, assignmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: MySubmissionPayload) =>
      assignmentsApi.submitMine(courseId as string, assignmentId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: mySubmissionKey(courseId as string, assignmentId) });
    },
  });
}

import { useQuery } from "@tanstack/react-query";

import { resultsApi } from "@/features/examinations/results/api/results-api";

export function useStudentCourseResult(studentId: string, courseId: string) {
  return useQuery({
    queryKey: ["examinations", "results", studentId, courseId],
    queryFn: () => resultsApi.getForStudentCourse(studentId, courseId),
    enabled: !!studentId && !!courseId,
    retry: false,
  });
}

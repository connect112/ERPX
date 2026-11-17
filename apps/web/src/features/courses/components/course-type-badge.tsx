import { Badge } from "@/components/ui/badge";
import type { CourseType } from "@/features/courses/api/courses-api";
import { courseTypeLabels } from "@/features/courses/schemas/course-schemas";

export function CourseTypeBadge({ type }: { type: CourseType }) {
  return <Badge variant={type === "internship" ? "info" : "outline"}>{courseTypeLabels[type]}</Badge>;
}

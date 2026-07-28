import { Badge } from "@/components/ui/badge";

export function CourseStatusBadge({ isPublished }: { isPublished: boolean }) {
  return (
    <Badge variant={isPublished ? "success" : "secondary"}>
      {isPublished ? "Published" : "Draft"}
    </Badge>
  );
}

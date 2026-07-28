import { GraduationCap } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyCourse } from "@/features/courses/api/courses-hooks";
import type { EnrollmentPublic } from "@/features/courses/api/courses-api";

interface EnrollmentListItemProps {
  enrollment: EnrollmentPublic;
}

export function EnrollmentListItem({ enrollment }: EnrollmentListItemProps) {
  const { data: course, isLoading } = useMyCourse(enrollment.course_id);

  return (
    <li className="flex items-center justify-between py-3">
      <div className="flex items-center gap-3">
        <GraduationCap className="h-4 w-4 text-muted-foreground" />
        {isLoading ? (
          <Skeleton className="h-4 w-40" />
        ) : (
          <span className="text-sm font-medium">{course?.title ?? "Untitled course"}</span>
        )}
      </div>
      <div className="flex items-center gap-3">
        <Badge variant="outline" className="capitalize">
          {enrollment.status}
        </Badge>
        <Link
          to={`/courses/${enrollment.course_id}`}
          className="text-sm font-medium text-primary hover:underline"
        >
          View
        </Link>
      </div>
    </li>
  );
}

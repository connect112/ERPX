import { GraduationCap } from "lucide-react";
import { Link } from "react-router-dom";

import type { MyCourseRef } from "@/features/my-internship/api/my-internship-api";
import { describeCourse } from "@/features/my-internship/lib/format";

export function LearningCourse({ course, lmsStatus }: { course: MyCourseRef | null; lmsStatus: "granted" | "revoked" }) {
  if (!course) return null;
  const open = lmsStatus === "granted" && course.accessible;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md bg-muted/40 p-3 text-sm" data-testid="learning-course">
      <GraduationCap className="h-4 w-4 text-muted-foreground" />
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Learning course</p>
        <p className="font-medium">{course.title}</p>
        {describeCourse(course) && <p className="text-xs text-muted-foreground">{describeCourse(course)}</p>}
      </div>
      {open ? (
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-emerald-700 dark:text-emerald-400">LMS access active</span>
          <Link to={`/courses/${course.id}`} className="text-sm font-medium text-primary hover:underline">
            Open course
          </Link>
        </div>
      ) : (
        <span className="ml-auto text-xs text-muted-foreground">{lmsStatus === "revoked" ? "Your access to this course was withdrawn." : "The course is not available to you yet."}</span>
      )}
    </div>
  );
}

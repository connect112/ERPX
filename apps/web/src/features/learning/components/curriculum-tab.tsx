import { ChaptersPanel } from "@/features/courses/chapters/components/chapters-panel";
import type { TabProps } from "@/features/learning/components/learning-workspace";

/** The curriculum is the course's: both pages show the same chapters, lessons and resources (the same `course_id`). */
export function CurriculumTab({ courseId, ctx }: TabProps) {
  if (!courseId) {
    return <p className="text-sm text-muted-foreground">No LMS course is linked yet, so there is no curriculum. Link one in Onboarding Settings → LMS course.</p>;
  }
  return (
    <div className="space-y-3">
      {!ctx.course_caps.curriculum_manage && (
        <p className="text-xs text-muted-foreground">You can read the curriculum. Editing it needs the course permission; managing an internship does not include it.</p>
      )}
      <ChaptersPanel courseId={courseId} />
    </div>
  );
}

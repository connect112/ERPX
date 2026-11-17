import type { TabProps } from "@/features/learning/components/learning-workspace";
import { ProjectsTab as InternshipProjects } from "@/features/our-internships/components/projects-tab";

/**
 * Projects belong to internships: the project engine (choices, submissions, reviews, final marks) is the internship's own, and this tab shows
 * those very records for the chosen internship. A course with no internship has no projects to show; it says so instead of offering controls
 * that would do nothing.
 */
export function ProjectsTab({ internship, needsChoice, courseId }: TabProps) {
  if (internship) return <InternshipProjects internshipId={internship.id} canManage={internship.can_manage} />;
  return (
    <div className="space-y-2 rounded-md border border-dashed p-6 text-sm" data-testid="projects-empty">
      <p className="font-medium">{needsChoice ? "Choose an internship to see its projects." : "This course has no internship projects."}</p>
      <p className="text-muted-foreground">
        {needsChoice
          ? "Projects belong to one internship, so each internship's are shown separately."
          : courseId
            ? "Projects are an internship feature: students choose a project, hand it in and are reviewed within an internship. Link this course to an internship to manage projects here."
            : "Link an LMS course to this internship to see it here."}
      </p>
    </div>
  );
}

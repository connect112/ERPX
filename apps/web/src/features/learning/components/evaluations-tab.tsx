import { useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ExamsPanel } from "@/features/examinations/exams/components/exams-panel";
import { AssessmentsManager } from "@/features/learning/components/assessments-manager";
import type { TabProps } from "@/features/learning/components/learning-workspace";
import { ResultsView } from "@/features/learning/components/results-view";
import { AssignmentsPanel } from "@/features/lms/assignments/components/assignments-panel";
import { AssignmentsTab as InternshipAssignments } from "@/features/our-internships/components/assignments-tab";
import { ExamsTab as InternshipExams } from "@/features/our-internships/components/exams-tab";

function Section({ title, hint, children, testId }: { title: string; hint: string; children: React.ReactNode; testId?: string }) {
  return (
    <section className="space-y-2" data-testid={testId}>
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
      {children}
    </section>
  );
}

/**
 * A course's own exams and assignments are shared by everyone enrolled in the course; they are not an internship's activities (those are made
 * above, through the internship's own workflow, and are graded and reported with it). On a course that serves internships they are tucked
 * away, clearly labelled and closed by default, so nobody creates one by mistake thinking it belongs to the internship. On a regular course
 * nothing changes: they are shown as before.
 */
function CourseWide({ serving, title, hint, testId, children }: { serving: boolean; title: string; hint: string; testId: string; children: React.ReactNode }) {
  if (!serving) {
    return (
      <Section title={title} hint={hint} testId={testId}>
        {children}
      </Section>
    );
  }
  return (
    <details className="rounded-md border bg-muted/20 p-3" data-testid={testId}>
      <summary className="cursor-pointer text-sm font-semibold">
        {title} <span className="ml-1 text-xs font-normal text-muted-foreground">(course-wide, not part of any internship)</span>
      </summary>
      <div className="mt-3 space-y-2">
        <p className="rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
          {hint} Anything added here is for everyone enrolled in the course. It is <strong>not</strong> an internship activity: it is not assigned to an internship's students, graded or reported with an internship. To add work for an internship, use the internship sections above.
        </p>
        {children}
      </div>
    </details>
  );
}

const ASK = <p className="text-sm text-muted-foreground">Choose an internship above to see its own activities.</p>;

/**
 * Evaluations: exams, assignments, assessments/quizzes and results in one place. Each kind keeps its own engine: an internship's exams are its
 * workshop exams, its assignments are the internship assignments, a course's exams and assignments are the course's own. This screen only
 * puts them side by side, each section working on the records that own it.
 */
export function EvaluationsTab(props: TabProps) {
  const { courseId, internship, needsChoice, ctx } = props;
  const [sub, setSub] = useState("exams");
  const caps = ctx.course_caps;
  const serving = ctx.internships.length > 0; // the course is linked to at least one internship
  const internshipSection = (render: (i: NonNullable<TabProps["internship"]>) => React.ReactNode) => (internship ? render(internship) : needsChoice ? ASK : null);

  return (
    <Tabs value={sub} onValueChange={setSub}>
      <TabsList>
        <TabsTrigger value="exams" data-testid="evaluations-exams">Exams</TabsTrigger>
        <TabsTrigger value="assignments" data-testid="evaluations-assignments">Assignments</TabsTrigger>
        <TabsTrigger value="assessments" data-testid="evaluations-assessments">Assessments / Quizzes</TabsTrigger>
        <TabsTrigger value="results" data-testid="evaluations-results">Results</TabsTrigger>
      </TabsList>

      <TabsContent value="exams" className="space-y-6">
        {internshipSection((i) => (
          <Section title="Internship exams" hint="This internship's exams: students are added from its selected list and take them through their personal link, which stops working when their access is withdrawn." testId="internship-exams">
            <InternshipExams internshipId={i.id} canManage={i.can_manage} />
          </Section>
        ))}
        {courseId && caps.exams_view && (
          <CourseWide serving={serving} title="Course exams" hint="The course's own exams." testId="course-exams">
            <ExamsPanel courseId={courseId} />
          </CourseWide>
        )}
      </TabsContent>

      <TabsContent value="assignments" className="space-y-6">
        {internshipSection((i) => (
          <Section title="Internship assignments" hint="This internship's assignments, submissions and grading. The same records are shown on the internship page." testId="internship-assignments">
            <InternshipAssignments internshipId={i.id} canManage={i.can_manage} />
          </Section>
        ))}
        {courseId && caps.assignments_view && (
          <CourseWide serving={serving} title="Course assignments" hint="The course's own assignments." testId="course-assignments">
            <AssignmentsPanel courseId={courseId} />
          </CourseWide>
        )}
      </TabsContent>

      <TabsContent value="assessments">
        {courseId ? <AssessmentsManager {...props} courseId={courseId} /> : <p className="text-sm text-muted-foreground">Assessments belong to the LMS course; link one to this internship to use them.</p>}
      </TabsContent>

      <TabsContent value="results">
        <ResultsView {...props} />
      </TabsContent>
    </Tabs>
  );
}

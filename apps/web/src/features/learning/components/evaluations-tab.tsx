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
          <Section title="Course exams" hint="The course's own exams, shared by everyone enrolled in the course." testId="course-exams">
            <ExamsPanel courseId={courseId} />
          </Section>
        )}
      </TabsContent>

      <TabsContent value="assignments" className="space-y-6">
        {internshipSection((i) => (
          <Section title="Internship assignments" hint="This internship's assignments, submissions and grading. The same records are shown on the internship page." testId="internship-assignments">
            <InternshipAssignments internshipId={i.id} canManage={i.can_manage} />
          </Section>
        ))}
        {courseId && caps.assignments_view && (
          <Section title="Course assignments" hint="The course's own assignments, shared by everyone enrolled in the course." testId="course-assignments">
            <AssignmentsPanel courseId={courseId} />
          </Section>
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

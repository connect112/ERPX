import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CurriculumAccessContext } from "@/features/courses/lib/curriculum-access";
import { type InternshipRef, type LearningContext, useLearningContext } from "@/features/learning/api/learning-api";
import { ActivityTab } from "@/features/learning/components/activity-tab";
import { CurriculumTab } from "@/features/learning/components/curriculum-tab";
import { DiscussionsTab } from "@/features/learning/components/discussions-tab";
import { EnrollmentsTab } from "@/features/learning/components/enrollments-tab";
import { EvaluationsTab } from "@/features/learning/components/evaluations-tab";
import { ProjectsTab } from "@/features/learning/components/projects-tab";
import { InternshipAccessContext } from "@/features/our-internships/lib/internship-access";

/** What every Learning tab is told: the course it works on, the internship (cohort) whose own activities it shows, and what the caller may do. */
export interface TabProps {
  courseId: string | null;
  internship: InternshipRef | null;
  /** the course page has several internships and none is chosen yet: internship-owned data waits for a choice */
  needsChoice: boolean;
  ctx: LearningContext;
  onTab: (tab: string) => void;
}

const selectClass = "rounded-md border bg-background px-3 py-2 text-sm";

/**
 * The Learning workspace. The internship page and the course page both render THIS component, so they show exactly the same tabs in the same
 * order (the list comes from the server, `GET /learning/context`) and use the same behaviour; only the scope differs:
 *   - on an internship: its own activities, and the linked course's curriculum;
 *   - on a course: the course's data, and (with a cohort chosen) that internship's own activities, from the very same records.
 * Nothing is copied between them, so a change made on either page is the other's the next time it looks.
 */
export function LearningWorkspace({
  courseId,
  internshipId,
  tab,
  onTabChange,
}: {
  courseId?: string;
  internshipId?: string;
  tab?: string;
  onTabChange?: (tab: string) => void;
}) {
  const context = useLearningContext({ courseId, internshipId });
  const [localTab, setLocalTab] = useState("curriculum");
  const [chosen, setChosen] = useState("");
  const current = tab ?? localTab;
  const change = (next: string) => (onTabChange ? onTabChange(next) : setLocalTab(next));

  if (context.isLoading) return <Skeleton className="h-64 w-full" />;
  if (context.isError || !context.data) return <p className="text-sm text-destructive">Could not load the learning workspace.</p>;

  const ctx = context.data;
  const internships = ctx.internships;
  const effectiveId = internshipId ?? (chosen || (internships.length === 1 ? internships[0].id : ""));
  const internship = internships.find((i) => i.id === effectiveId) ?? null;
  const resolvedCourse = ctx.course?.id ?? null;
  const props: TabProps = { courseId: resolvedCourse, internship, needsChoice: !internshipId && ctx.needs_selector && !internship, ctx, onTab: change };

  return (
    <CurriculumAccessContext.Provider value={{ canManage: !!ctx.course_caps.curriculum_manage }}>
      <InternshipAccessContext.Provider value={{ role: internship?.can_delete === false ? "instructor" : "admin", canDelete: internship?.can_delete ?? true, accessUntil: null }}>
        <div className="space-y-4" data-testid="learning-workspace">
          {!internshipId && internships.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 text-sm" data-testid="cohort-selector">
              <label htmlFor="cohort" className="font-medium">
                Internship
              </label>
              {internships.length > 1 ? (
                <select id="cohort" className={selectClass} value={effectiveId} onChange={(e) => setChosen(e.target.value)}>
                  <option value="">Choose an internship…</option>
                  {internships.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.title}
                    </option>
                  ))}
                </select>
              ) : (
                <Badge variant="secondary">{internships[0].title}</Badge>
              )}
              <span className="text-muted-foreground">
                {internship ? "Showing this internship's own activities, students and results with the course's." : "Internship-owned activities, students and results are shown for one internship at a time."}
              </span>
            </div>
          )}
          {internshipId && !ctx.course && (
            <p className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
              This internship has no LMS course yet. Its own activities work now; the curriculum appears once a course is linked in Onboarding Settings.
            </p>
          )}

          <Tabs value={current} onValueChange={change}>
            <TabsList className="h-auto max-w-full flex-wrap justify-start">
              {ctx.tabs.map((t) => (
                <TabsTrigger key={t.key} value={t.key} data-testid={`learning-tab-${t.key}`}>
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value="curriculum">
              <CurriculumTab {...props} />
            </TabsContent>
            <TabsContent value="enrollments">
              <EnrollmentsTab {...props} />
            </TabsContent>
            <TabsContent value="evaluations">
              <EvaluationsTab {...props} />
            </TabsContent>
            <TabsContent value="projects">
              <ProjectsTab {...props} />
            </TabsContent>
            <TabsContent value="discussions">
              <DiscussionsTab {...props} />
            </TabsContent>
            <TabsContent value="practicals">
              <ActivityTab kind="practicals" {...props} />
            </TabsContent>
            <TabsContent value="viva">
              <ActivityTab kind="viva" {...props} />
            </TabsContent>
          </Tabs>
        </div>
      </InternshipAccessContext.Provider>
    </CurriculumAccessContext.Provider>
  );
}

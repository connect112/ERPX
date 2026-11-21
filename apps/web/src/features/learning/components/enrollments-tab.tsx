import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EnrollmentsByCoursePanel } from "@/features/lms/enrollment/components/enrollments-by-course-panel";
import { errorMessage } from "@/features/institutions/lib/format";
import { type EnrollmentRow, learningKeys, useLearningEnrollments } from "@/features/learning/api/learning-api";
import type { TabProps } from "@/features/learning/components/learning-workspace";
import { onboardingApi, ourInternshipsKeys } from "@/features/our-internships/api/our-internships-api";

const accessBadge: Record<EnrollmentRow["lms_status"], { label: string; variant: "success" | "secondary" | "warning" }> = {
  granted: { label: "Access granted", variant: "success" },
  not_granted: { label: "Not granted", variant: "secondary" },
  revoked: { label: "Revoked", variant: "warning" },
};
const provenanceText = { internship: "Through this internship", independent: "Enrolled independently (kept if access is revoked)" } as const;

function InternshipEnrollments({ internshipId, canManage }: { internshipId: string; canManage: boolean }) {
  const queryClient = useQueryClient();
  const view = useLearningEnrollments(internshipId);
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: learningKeys.all });
    void queryClient.invalidateQueries({ queryKey: ourInternshipsKeys.all });
  };
  const grant = useMutation({ mutationFn: (studentId: string) => onboardingApi.grant(internshipId, studentId), onSuccess: refresh });
  const revoke = useMutation({ mutationFn: (studentId: string) => onboardingApi.revoke(internshipId, studentId), onSuccess: refresh });
  const error = grant.error ?? revoke.error;

  if (view.isLoading) return <Skeleton className="h-40 w-full" />;
  if (view.isError || !view.data) return <p className="text-sm text-destructive">Could not load the enrollments.</p>;
  const { rows, independent } = view.data;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Selected students and their LMS access</CardTitle>
          <p className="text-sm text-muted-foreground">
            The internship decides who may learn: access is granted and withdrawn here, through the internship's own workflow. Withdrawing it keeps
            the student's records and any enrollment they held on their own.
          </p>
        </CardHeader>
        <CardContent>
          {error && <p className="mb-3 text-sm text-destructive">{errorMessage(error, "That did not work.")}</p>}
          {rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">No students are selected on this internship yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Stage</TableHead>
                  <TableHead>LMS access</TableHead>
                  <TableHead>Enrollment</TableHead>
                  <TableHead>Progress</TableHead>
                  {canManage && <TableHead className="text-right">Action</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => {
                  const badge = accessBadge[r.lms_status];
                  return (
                    <TableRow key={r.selection_id} data-testid={`enrollment-row-${r.email}`}>
                      <TableCell>
                        <div className="font-medium">{r.name}</div>
                        <div className="text-xs text-muted-foreground">{r.email}</div>
                      </TableCell>
                      <TableCell className="text-sm">{r.stage_label}</TableCell>
                      <TableCell>
                        <Badge variant={badge.variant}>{badge.label}</Badge>
                        {r.has_account && <div className="mt-1 text-xs text-muted-foreground">LMS account created</div>}
                        {r.lms_status !== "granted" && r.grant_blockers.length > 0 && (
                          <ul className="mt-1 list-disc pl-4 text-xs text-muted-foreground">
                            {r.grant_blockers.map((b) => (
                              <li key={b}>{b}</li>
                            ))}
                          </ul>
                        )}
                      </TableCell>
                      <TableCell className="text-sm">
                        {r.enrollment_status ? (
                          <>
                            <span className="capitalize">{r.enrollment_status}</span>
                            {r.provenance && <div className="text-xs text-muted-foreground">{provenanceText[r.provenance]}</div>}
                          </>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm">
                        {r.progress_percent != null ? `${r.progress_percent}% (${r.completed_lessons}/${r.total_lessons} lessons)` : <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      {canManage && (
                        <TableCell className="text-right">
                          {r.lms_status === "granted" ? (
                            <Button size="sm" variant="outline" disabled={revoke.isPending} onClick={() => window.confirm(`Withdraw ${r.name}'s LMS access? Their records are kept.`) && revoke.mutate(r.student_id)}>
                              Revoke access
                            </Button>
                          ) : (
                            <Button size="sm" disabled={grant.isPending || r.grant_blockers.length > 0} onClick={() => grant.mutate(r.student_id)}>
                              {r.lms_status === "revoked" ? "Grant again" : "Grant access"}
                            </Button>
                          )}
                        </TableCell>
                      )}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {independent && independent.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Enrolled in the course independently</CardTitle>
            <p className="text-sm text-muted-foreground">These students are not selected on this internship, so they have no access to its activities. They are managed under the course.</p>
          </CardHeader>
          <CardContent>
            <ul className="divide-y text-sm">
              {independent.map((i) => (
                <li key={i.enrollment_id} className="flex justify-between py-2">
                  <span>{i.name}</span>
                  <span className="capitalize text-muted-foreground">{i.status}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export function EnrollmentsTab({ courseId, internship, needsChoice, ctx }: TabProps) {
  return (
    <div className="space-y-6">
      {internship && <InternshipEnrollments internshipId={internship.id} canManage={internship.can_manage} />}
      {needsChoice && <p className="text-sm text-muted-foreground">Choose an internship above to see its students and their LMS access.</p>}
      {courseId && ctx.course_caps.enrollments_view && (
        <div className="space-y-2">
          {internship && (
            <p className="text-xs text-muted-foreground">
              Course enrollments (managed under the course). Access that an internship granted can only be withdrawn from the internship above.
            </p>
          )}
          <EnrollmentsByCoursePanel courseId={courseId} />
        </div>
      )}
      {!internship && !needsChoice && (!courseId || !ctx.course_caps.enrollments_view) && <p className="text-sm text-muted-foreground">There is nothing to show here for your access.</p>}
    </div>
  );
}

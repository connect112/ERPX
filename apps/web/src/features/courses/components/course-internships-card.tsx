import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CoursePublic } from "@/features/courses/api/courses-api";
import { InternshipPicker } from "@/features/courses/components/internship-picker";
import { useLinkableInternships } from "@/features/courses/lib/linkable-internships";
import { feeText } from "@/features/courses/lib/fee";
import { errorMessage } from "@/features/institutions/lib/format";
import { onboardingApi, ourInternshipsKeys } from "@/features/our-internships/api/our-internships-api";

/** The internships that use this internship course, with link and unlink. The only link is the internship's own course setting. */
export function CourseInternshipsCard({ course }: { course: CoursePublic }) {
  const queryClient = useQueryClient();
  const { internships } = useLinkableInternships();
  const [pick, setPick] = useState("");
  const [replace, setReplace] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const picked = internships.find((i) => i.id === pick);
  const replacing = !!picked?.lms_course_id;

  const changed = () => {
    void queryClient.invalidateQueries({ queryKey: ["courses"] });
    void queryClient.invalidateQueries({ queryKey: ourInternshipsKeys.all });
  };
  const run = async (internshipId: string, courseId: string | null, confirm: boolean) => {
    setBusy(true);
    setProblem(null);
    try {
      await onboardingApi.setCourse(internshipId, courseId, confirm);
      setPick("");
      setReplace(false);
    } catch (e) {
      setProblem(errorMessage(e, "That did not work."));
    } finally {
      setBusy(false);
      changed();
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Internships</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {course.linked_internships.length === 0 ? (
          <p className="text-sm text-muted-foreground">Not linked to an internship</p>
        ) : (
          <ul className="space-y-2">
            {course.linked_internships.map((i) => (
              <li key={i.id} className="flex items-start justify-between gap-3 text-sm">
                <div>
                  <Link className="font-medium text-primary hover:underline" to={`/our-internships/${i.id}?tab=onboarding-settings&section=lms-course`}>
                    {i.title}
                  </Link>
                  {i.fee && <p className="text-xs text-muted-foreground">Fee: {feeText(i.fee)}</p>}
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={busy}
                  aria-label={`Unlink ${i.title}`}
                  onClick={() => window.confirm(`Unlink "${i.title}" from this course?`) && void run(i.id, null, true)}
                >
                  Unlink
                </Button>
              </li>
            ))}
          </ul>
        )}
        {course.course_type === "internship" && (
          <div className="space-y-2 border-t pt-3">
            <label className="text-sm font-medium" htmlFor="link-internship">
              Link to an internship
            </label>
            <InternshipPicker id="link-internship" value={pick} onChange={(v) => (setPick(v), setReplace(false))} exclude={course.linked_internships.map((i) => i.id)} disabled={busy} />
            {replacing && (
              <label className="flex items-start gap-2 rounded-md bg-amber-50 p-2 text-sm text-amber-900 dark:bg-amber-500/10 dark:text-amber-200">
                <input type="checkbox" className="mt-1" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
                <span>
                  This internship already uses <strong>{picked?.lms_course_title}</strong>. Replace it with this course.
                </span>
              </label>
            )}
            <Button type="button" size="sm" disabled={!pick || busy || (replacing && !replace)} onClick={() => void run(pick, course.id, replace)}>
              Link
            </Button>
            {problem && (
              <p className="text-sm text-destructive" role="alert">
                {problem}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

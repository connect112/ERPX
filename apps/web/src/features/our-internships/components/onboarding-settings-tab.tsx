import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { errorMessage } from "@/features/institutions/lib/format";
import { OnboardingSettingsPanel } from "@/features/internship-onboarding/components/flow-panel";
import { type OurInternship, onboardingApi, ourInternshipsKeys } from "@/features/our-internships/api/our-internships-api";

const selectClass = "rounded-md border bg-background px-3 py-2 text-sm";

/** The internship's LMS course: students given LMS access are enrolled in it. Chosen once for the whole internship. */
function LmsCourseCard({ internship }: { internship: OurInternship }) {
  const queryClient = useQueryClient();
  const courses = useQuery({ queryKey: ["our-internships", "courses", internship.id], queryFn: () => onboardingApi.courses(internship.id) });
  const setCourse = useMutation({
    mutationFn: (courseId: string | null) => onboardingApi.setCourse(internship.id, courseId, !!internship.lms_course_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ourInternshipsKeys.all }),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">LMS course</CardTitle>
        <CardDescription>
          Students given LMS access are enrolled in this course on lms.pentrix.in. Whether access is granted automatically is set under
          Settings (LMS access).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <select
          aria-label="LMS course"
          className={`${selectClass} w-full max-w-md`}
          value={internship.lms_course_id ?? ""}
          disabled={setCourse.isPending}
          onChange={(e) => {
            const next = e.target.value || null;
            const current = internship.lms_course_title ?? "the current course";
            // changing a course that is already chosen is asked about first; the server still refuses it once students are enrolled
            if (internship.lms_course_id && next !== internship.lms_course_id && !window.confirm(`This internship already uses "${current}". Replace it?`)) return;
            setCourse.mutate(next);
          }}
        >
          <option value="">Choose a course...</option>
          {courses.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title}
              {c.is_published ? "" : " (not published)"}
            </option>
          ))}
        </select>
        {courses.data?.length === 0 && <p className="text-xs text-muted-foreground">There are no courses yet. Create one under Courses first.</p>}
        {!internship.lms_course_id && <p className="text-xs text-amber-700 dark:text-amber-400">Choose the course before granting access.</p>}
        {setCourse.isError && <p className="text-sm text-destructive">{errorMessage(setCourse.error, "Could not save the course.")}</p>}
      </CardContent>
    </Card>
  );
}

/** How this internship onboards: mode, fees, payment methods and accounts, refunds, form, documents, deadlines, LMS, templates. */
export function OnboardingSettingsTab({ internship, isAdmin }: { internship: OurInternship; isAdmin: boolean }) {
  return <OnboardingSettingsPanel internshipId={internship.id} isAdmin={isAdmin} lmsCourse={<LmsCourseCard internship={internship} />} />;
}

import { useEffect, useState } from "react";

import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import {
  isStudentOnly,
  markRedirected,
  redirectedRecently,
  studentPortalUrl,
} from "@/features/auth/lib/student-portal-redirect";
import { useIsEmployee } from "@/features/employee-self-service/lib/use-is-employee";
import { useIsStudent } from "@/features/student-self-service/lib/use-is-student";
import { useIsTrainer } from "@/features/trainer-self-service/lib/use-is-trainer";

/**
 * Sends an account that is only a student to the student site (lms.pentrix.in). Renders nothing until it knows; then
 * either shows a short "taking you there" cover while the browser moves, or nothing at all.
 */
export function StudentPortalRedirect() {
  const roles = useMyRoles();
  const student = useIsStudent();
  const trainer = useIsTrainer();
  const employee = useIsEmployee();
  const [leaving, setLeaving] = useState(false);

  const known = !!roles.data && !student.isLoading && !trainer.isLoading && !employee.isLoading;
  const studentOnly =
    known &&
    isStudentOnly({
      isStudent: student.isStudent,
      isTrainer: trainer.isTrainer,
      isEmployee: employee.isEmployee,
      isSuperuser: roles.data?.is_superuser ?? false,
      roleSlugs: (roles.data?.roles ?? []).map((r) => r.slug),
    });

  useEffect(() => {
    if (!studentOnly) return;
    const target = studentPortalUrl();
    // No student site for this address (local development), or we just came back from it: stay here.
    if (!target || redirectedRecently()) return;
    markRedirected();
    setLeaving(true);
    window.location.replace(target);
  }, [studentOnly]);

  if (!leaving) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background text-sm text-muted-foreground">
      Taking you to the student portal...
    </div>
  );
}

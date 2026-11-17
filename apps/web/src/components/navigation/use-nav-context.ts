import { useMemo } from "react";

import type { NavContext } from "@/components/navigation/access";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import { useIsEmployee } from "@/features/employee-self-service/lib/use-is-employee";
import { useIsStudent } from "@/features/student-self-service/lib/use-is-student";
import { useIsTrainer } from "@/features/trainer-self-service/lib/use-is-trainer";

/** The signed-in user as the navigation sees them (union of every role's permissions, plus the self-service records they have). */
export function useNavContext(): NavContext & { isLoading: boolean } {
  const { data, isLoading: rolesLoading } = useMyRoles();
  const { isTrainer, isLoading: trainerLoading } = useIsTrainer();
  const { isEmployee, isLoading: employeeLoading } = useIsEmployee();
  const { isStudent, isLoading: studentLoading } = useIsStudent();
  const permissions = data?.effective_permissions;
  const isSuperuser = data?.is_superuser ?? false;
  return useMemo(
    () => ({ permissions: permissions ?? [], isSuperuser, isTrainer, isEmployee, isStudent, isLoading: rolesLoading || trainerLoading || employeeLoading || studentLoading }),
    [permissions, isSuperuser, isTrainer, isEmployee, isStudent, rolesLoading, trainerLoading, employeeLoading, studentLoading]
  );
}

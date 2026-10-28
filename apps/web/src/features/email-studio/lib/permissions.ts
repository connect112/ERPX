import { useMyRoles } from "@/features/auth/api/authorization-hooks";

/** What this person may do in Email Studio. The server checks every one of these again; this only decides what to show. */
export function useStudioPermissions() {
  const roles = useMyRoles();
  const data = roles.data;
  const has = (code: string) => !!data && (data.is_superuser || data.effective_permissions.includes(code));
  return {
    loaded: !!data,
    canManage: has("email_templates.manage"),
    canPublish: has("email_templates.publish"),
    canUseStudents: has("our_internships.view"),
  };
}

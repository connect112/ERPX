import { useMyRoles } from "@/features/auth/api/authorization-hooks";

/** Whether this person may make a lead from the inbox: they need to read the inbox and to manage CRM leads. */
export function useCanCreateLead(): boolean {
  const me = useMyRoles();
  const permissions = me.data?.effective_permissions ?? [];
  return (me.data?.is_superuser ?? false) || (permissions.includes("social_media.inbox") && permissions.includes("crm.leads.manage"));
}

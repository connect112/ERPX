import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { AuditAction } from "@/features/audit/api/audit-api";

const actionVariants: Record<AuditAction, BadgeProps["variant"]> = {
  create: "success",
  update: "info",
  delete: "destructive",
};

const actionLabels: Record<AuditAction, string> = {
  create: "Created",
  update: "Updated",
  delete: "Deleted",
};

export function AuditActionBadge({ action }: { action: AuditAction }) {
  return <Badge variant={actionVariants[action]}>{actionLabels[action]}</Badge>;
}

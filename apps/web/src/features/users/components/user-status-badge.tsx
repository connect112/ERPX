import { Badge, type BadgeProps } from "@/components/ui/badge";
import { type UserStatus, userStatusLabels } from "@/features/users/schemas/user-schemas";

const statusVariants: Record<UserStatus, BadgeProps["variant"]> = {
  pending_verification: "warning",
  active: "success",
  suspended: "destructive",
  deactivated: "secondary",
};

export function UserStatusBadge({ status }: { status: UserStatus }) {
  return <Badge variant={statusVariants[status]}>{userStatusLabels[status]}</Badge>;
}
